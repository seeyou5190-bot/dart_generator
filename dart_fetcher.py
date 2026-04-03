"""dart_fetcher.py - DART API 데이터 수집 및 PDF 파싱 모듈"""

import io
import logging
import re
import time
from dataclasses import dataclass, field

import OpenDartReader
import pdfplumber
import requests

logger = logging.getLogger(__name__)


@dataclass
class FinancialStatement:
    company_name:   str
    short_name:     str
    period_label:   str
    balance_sheet:  dict = field(default_factory=dict)
    income_stmt:    dict = field(default_factory=dict)
    raw_bs:         dict = field(default_factory=dict)  # 전체 원본 데이터
    raw_is:         dict = field(default_factory=dict)  # 전체 원본 데이터
    raw_report_files: list = field(default_factory=list)  # 다운로드된 원본 보고서 파일
    unit_won:       int  = 1_000_000
    source_type:    str  = "DART"
    errors:         list = field(default_factory=list)

    def get_unit_label(self) -> str:
        return {1: "원", 1_000: "천원", 1_000_000: "백만원",
                100_000_000: "억원"}.get(self.unit_won, "원")


class DartFetcher:
    REPORT_CODE = {1: "11013", 2: "11012", 3: "11014", 4: "11011"}
    QUARTER_KW  = {1: "1분기", 2: "반기", 3: "3분기", 4: "사업보고서"}

    def __init__(self, api_key: str):
        self.dart = OpenDartReader(api_key)
        self._corp_cache: dict = {}

    def fetch(self, company_cfg, year, quarter, bs_accounts, is_accounts,
              mapper_bs, mapper_is, raw_dir=None) -> "FinancialStatement":
        dart_name  = company_cfg["dart_name"]
        short_name = company_cfg["short_name"]
        # 설정파일의 corp_code보다 DART API 검색 결과를 우선합니다 (최신 상태 유지)
        corp_code  = self._get_corp_code(dart_name) or company_cfg.get("corp_code", "")
        period_lbl = self._period_label(year, quarter)
        fs = FinancialStatement(dart_name, short_name, period_lbl)

        try:
            report = self._find_report(dart_name, year, quarter)
            if not report:
                fs.errors.append(f"{period_lbl} 보고서를 찾을 수 없습니다.")
                return fs

            rcept_no = report["rcept_no"]
            logger.info(f"  접수번호: {rcept_no}")

            # 원본 보고서 파일(첨부)을 저장
            if raw_dir:
                fs.raw_report_files = self._download_report_files(rcept_no, short_name, year, quarter, raw_dir)

            # XBRL 우선, 실패 시 PDF
            parsed = self._parse_xbrl(corp_code, year, quarter)
            if not parsed:
                logger.info(f"  XBRL 실패 → PDF 파싱 시도")
                parsed = self._parse_pdf(rcept_no)

            if not parsed:
                fs.errors.append("재무제표 데이터를 추출할 수 없습니다.")
                return fs

            raw_bs, raw_is, unit_won = parsed
            fs.unit_won      = unit_won
            fs.raw_bs        = raw_bs
            fs.raw_is        = raw_is
            fs.balance_sheet = self._apply_mapping(raw_bs, mapper_bs)
            fs.income_stmt   = self._apply_mapping(raw_is, mapper_is)

        except Exception as e:
            logger.exception(f"{dart_name} 처리 중 예외")
            fs.errors.append(str(e))

        return fs

    # ── DART 조회 ──────────────────────────────────────
    def _get_corp_code(self, dart_name: str):
        if dart_name in self._corp_cache:
            return self._corp_cache[dart_name]
        try:
            code = self.dart.find_corp_code(dart_name)
            if code:
                self._corp_cache[dart_name] = code
            return code
        except Exception as e:
            logger.error(f"회사코드 조회 실패: {e}")
            return None

    def _find_report(self, dart_name, year, quarter):
        """dart.list()는 회사명으로 검색해야 합니다."""
        try:
            df = self.dart.list(dart_name, start=f"{year}0101",
                                end=f"{year}1231", kind="A")
            if df is None or df.empty:
                return None

            if quarter == 1:
                mask = df["report_nm"].str.contains("분기", na=False) & df["report_nm"].str.contains(".03", na=False)
            elif quarter == 2:
                mask = df["report_nm"].str.contains("반기", na=False)
            elif quarter == 3:
                mask = df["report_nm"].str.contains("분기", na=False) & df["report_nm"].str.contains(".09", na=False)
            else:
                mask = df["report_nm"].str.contains("사업보고서", na=False)

            filtered = df[mask]
            # 가장 최근 접수된 보고서를 가져옵니다. (기재정정 등이 있을 수 있으므로)
            return filtered.iloc[0].to_dict() if not filtered.empty else None
        except Exception as e:
            logger.error(f"보고서 목록 조회 실패: {e}")
            return None

    def _download_report_files(self, rcept_no: str, short_name: str, year: int, quarter: int, out_dir: str) -> list:
        if not out_dir:
            return []
        try:
            att = self.dart.attach_file_list(rcept_no)
            if not att:
                return []

            os.makedirs(out_dir, exist_ok=True)
            saved = []
            for fname, url in att.items():
                ext = fname.lower().rsplit('.', 1)[-1] if '.' in fname else ''
                if ext not in ("pdf", "hwp", "xlsx", "xls", "xbrl", "xml", "zip", "html"):
                    continue

                safe_name = re.sub(r"[^0-9a-zA-Z가-힣._-]", "_", fname)
                target = os.path.join(out_dir, f"{short_name}_{year}Q{quarter}_{safe_name}")

                # 캐시: 이미 다운로드했다면 중단
                if os.path.exists(target):
                    saved.append(target)
                    continue

                contents = self._download(url)
                if not contents:
                    continue

                with open(target, "wb") as f:
                    f.write(contents)
                saved.append(target)

            return saved
        except Exception as e:
            logger.error(f"원본보고서 다운로드 실패: {e}")
            return []

    # ── XBRL 파싱 ─────────────────────────────────────
    def _parse_xbrl(self, corp_code, year, quarter):
        try:
            rc   = self.REPORT_CODE.get(quarter, "11011")
            df   = self.dart.finstate(corp_code, year, reprt_code=rc)
            if df is None or df.empty:
                return None
            raw_bs = self._xbrl_to_dict(df, "BS")
            raw_is = self._xbrl_to_dict(df, "IS")
            unit   = self._detect_unit_xbrl(df)
            return raw_bs, raw_is, unit
        except Exception as e:
            logger.debug(f"XBRL 파싱 오류: {e}")
            return None

    @staticmethod
    def _xbrl_to_dict(df, _sj_div) -> dict:
        result = {}
        if df is None or df.empty:
            return result
        for _, row in df.iterrows():
            acct = str(row.get("account_nm", "")).strip()
            for col in ["thstrm_amount", "thstrm_add_amount", "frmtrm_amount"]:
                val = row.get(col)
                if val is not None and str(val).strip() not in ("", "-", "nan"):
                    try:
                        result[acct] = float(str(val).replace(",", ""))
                    except ValueError:
                        result[acct] = None
                    break
        return result

    @staticmethod
    def _detect_unit_xbrl(df) -> int:
        for col in df.columns:
            if "unit" in col.lower():
                val = str(df[col].iloc[0]).lower()
                if "백만" in val: return 1_000_000
                if "천" in val:   return 1_000
        return 1_000_000

    # ── PDF 파싱 ──────────────────────────────────────
    def _parse_pdf(self, rcept_no: str):
        try:
            # OpenDartReader 0.2.x uses attach_file_list/attach_files which returns a dict: {filename: url}
            att = self.dart.attach_file_list(rcept_no)
            if not att:
                return None
            pdf_url = None
            for fname, url in att.items():
                fname_lower = fname.lower()
                if fname_lower.endswith(".pdf"):
                    if any(kw in fname_lower for kw in ["재무", "financial", "fs", "별지", "보고서"]):
                        pdf_url = url; break
            if not pdf_url:
                for fname, url in att.items():
                    if fname.lower().endswith(".pdf"):
                        pdf_url = url; break
            if not pdf_url:
                return None
            pdf_bytes = self._download(pdf_url)
            return self._extract_pdf(pdf_bytes) if pdf_bytes else None
        except Exception as e:
            logger.error(f"PDF 파싱 오류: {e}")
            return None

    @staticmethod
    def _download(url: str, retries: int = 5):
        import time
        for i in range(retries):
            try:
                r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                if r.status_code == 429:
                    wait = 10 * (i + 1)
                    logger.warning(f"429 Too Many Requests: 대기 {wait}초 후 재시도")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.content
            except requests.exceptions.RequestException as e:
                logger.warning(f"다운로드 실패({i+1}/{retries}): {e}")
                # 점진적 지수 백오프
                time.sleep(min(60, 2 ** i))
        return None

    def _extract_pdf(self, pdf_bytes: bytes):
        import tempfile
        from pathlib import Path
        import pandas as pd
        import opendataloader_pdf
        import pdfplumber

        unit = 1_000_000
        with tempfile.TemporaryDirectory() as td:
            pdf_path = Path(td) / "temp.pdf"
            pdf_path.write_bytes(pdf_bytes)

            pages = []
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = (page.extract_text() or "")
                    text_ns = text.replace(" ", "")
                    if any(k in text_ns for k in ["재무상태표", "손익계산서", "포괄손익", "재무제표"]):
                        pages.append(str(i+1))
                        unit = self._detect_unit_text(text) or unit

            if not pages:
                return None

            out_dir = Path(td) / "out"
            out_dir.mkdir()

            try:
                import os
                jre_path = Path(__file__).parent / ".venv" / "jre" / "bin"
                if jre_path.exists() and str(jre_path) not in os.environ["PATH"]:
                    os.environ["PATH"] = str(jre_path) + os.pathsep + os.environ["PATH"]

                # Hancom SDK 구동
                opendataloader_pdf.convert(
                    str(pdf_path),
                    output_dir=str(out_dir),
                    format="html",
                    pages=",".join(pages)
                )
            except Exception as e:
                logger.error(f"Hancom SDK 오류: {e}")
                return None

            html_files = list(out_dir.glob("*.html"))
            if not html_files:
                return None

            try:
                with open(html_files[0], "r", encoding="utf-8") as f:
                    html_str = f.read()
                dfs = pd.read_html(io.StringIO(html_str))

                combined = {}
                for df in dfs:
                    parsed = self._parse_dataframe(df)
                    if parsed:
                        combined.update(parsed)

                if not combined:
                    return None

                return combined, combined, unit
            except Exception as e:
                logger.error(f"HTML 파싱 오류: {e}")
                return None

    @staticmethod
    def _detect_unit_text(text: str):
        t = text.replace(" ", "")
        if "단위:백만원" in t or "(백만원)" in t: return 1_000_000
        if "단위:천원"   in t or "(천원)"   in t: return 1_000
        if "단위:억원"   in t or "(억원)"   in t: return 100_000_000
        if "단위:원"     in t:                      return 1
        return None

    @staticmethod
    def _parse_dataframe(df) -> dict:
        import pandas as pd
        result = {}
        if df is None or df.empty:
            return result

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(-1)

        for _, row in df.iterrows():
            acct_parts = []
            for i in range(min(3, len(row))):
                val = row.iloc[i]
                if pd.isna(val): continue
                sval = str(val).strip()
                # 숫자가 들어가있지 않고 문자열이면 계정과목의 일부
                if sval and not any(c.isdigit() for c in sval):
                    acct_parts.append(sval)
                else:
                    break
            if not acct_parts:
                acct_parts = [str(row.iloc[0])]

            acct = " ".join(acct_parts)
            acct = re.sub(r"[\n\r\t]+", " ", acct).strip()
            if len(acct) < 2:
                continue

            amount = None
            for cell in row.iloc[len(acct_parts):]:
                if pd.isna(cell): continue
                cs = str(cell).replace(",", "").replace(" ", "")
                neg = cs.startswith("(") and cs.endswith(")") or cs.startswith("△")
                cs = cs.lstrip("△").strip("()")
                try:
                    amount = float(cs) * (-1 if neg else 1)
                    break
                except ValueError:
                    continue

            if amount is not None:
                result[acct] = amount
        return result

    @staticmethod
    def _apply_mapping(raw: dict, mapper) -> dict:
        result = {}
        for raw_name, amount in raw.items():
            std = mapper.map(raw_name)
            if std and std not in result:
                result[std] = amount
        return result

    @staticmethod
    def _period_label(year, quarter) -> str:
        lbl = {1:"1분기",2:"반기",3:"3분기",4:"연간"}
        return f"{year}년 {lbl.get(quarter,'?분기')}"
