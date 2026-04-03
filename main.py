"""main.py - 손해보험사 DART 재무제표 수집·엑셀 변환 메인"""

import argparse
import logging
import os
import sys
from pathlib import Path

import yaml

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# Add the current directory to the path to resolve imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from account_mapper import AccountMapper
from dart_fetcher    import DartFetcher
from excel_writer    import ExcelWriter
log_path = os.path.join(os.path.dirname(__file__), "logs", "dart_insurance.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def load_config(path="config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

def run(config: dict, log_callback=None):
    # 내부 로그 함수 정의 (웹 UI와 터미널 모두 출력)
    def log(msg=""):
        if log_callback:
            log_callback(msg)
        logger.info(msg) if msg else logger.info("")

    api_key  = config["dart"]["api_key"]
    if "YOUR_DART" in api_key:
        log("\n  config.yaml에 DART API 키를 입력하세요.")
        sys.exit(1)

    year     = config["period"]["year"]
    quarter  = config["period"]["quarter"]
    companies = config["companies"]
    bs_cfg   = config.get("balance_sheet_accounts", [])
    is_cfg   = config.get("income_statement_accounts", [])

    out_dir = config.get("output", {}).get("directory", "output")
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    raw_dir = os.path.join(out_dir, "raw_reports")
    os.makedirs(raw_dir, exist_ok=True)

    # AccountMapper 초기화 (수동/자동 처리는 내부 input 예외로 대응)
    mapper_bs = AccountMapper(bs_cfg)
    mapper_is = AccountMapper(is_cfg)
    mapper_bs.load_user_decisions("logs/user_mapping_bs.json")
    mapper_is.load_user_decisions("logs/user_mapping_is.json")

    fetcher = DartFetcher(api_key)
    statements = []
    total = len(companies)
    log("🔥 run() 시작됨")
    log()
    log("=" * 60)
    log(f"  손해보험사 재무제표 수집")
    log(f"  대상: {total}개사  |  {year}년 {quarter}분기")
    log("=" * 60)

    for i, co in enumerate(companies, 1):
        log(f"\n[{i}/{total}] {co['short_name']} 처리 중...")
        fs = fetcher.fetch(co, year, quarter, bs_cfg, is_cfg, mapper_bs, mapper_is, raw_dir=raw_dir)
        statements.append(fs)
        if fs.errors:
            for e in fs.errors: log(f"  ⚠ {e}")
        else:
            bs_n = sum(1 for v in fs.balance_sheet.values() if v is not None)
            is_n = sum(1 for v in fs.income_stmt.values()   if v is not None)
            log(f"  ✓ 재무상태표 {bs_n}건 / 손익계산서 {is_n}건")

    mapper_bs.save_user_decisions("logs/user_mapping_bs.json")
    mapper_is.save_user_decisions("logs/user_mapping_is.json")

    bs_stds = [a["standard"] for a in bs_cfg]
    is_stds = [a["standard"] for a in is_cfg]

    q_lbl   = {1:"1Q",2:"2Q",3:"3Q",4:"FY"}.get(quarter, str(quarter))
    fname   = f"손해보험사_재무제표_{year}{q_lbl}.xlsx"
    out_path = os.path.join(out_dir, fname)

    all_raw_files = []
    for fs in statements:
        if fs.raw_report_files:
            all_raw_files.extend(fs.raw_report_files)

    ExcelWriter(config).write(statements, bs_stds, is_stds, out_path)

    ok_cnt  = sum(1 for fs in statements if not fs.errors)
    err_cnt = total - ok_cnt
    log()
    log("=" * 60)
    log(f"  완료!  성공 {ok_cnt}개사 / 실패 {err_cnt}개사")
    log(f"  저장 위치: {os.path.abspath(out_path)}")
    log("=" * 60)

    failed = [fs for fs in statements if fs.errors]
    if failed:
        log("\n  [실패 목록]")
        for fs in failed:
            for e in fs.errors:
                log(f"  - {fs.short_name}: {e}")

    return {
        "excel": out_path,
        "raw_files": all_raw_files,
    }


def parse_args():
    p = argparse.ArgumentParser(description="DART 손해보험사 재무제표 → 엑셀")
    p.add_argument("--config",  default="config.yaml")
    p.add_argument("--year",    type=int)
    p.add_argument("--quarter", type=int, choices=[1,2,3,4])
    p.add_argument("--companies")
    p.add_argument("--api-key", dest="api_key")
    return p.parse_args()


if __name__ == "__main__":
    args   = parse_args()
    config = load_config(args.config)
    if args.year:     config["period"]["year"]    = args.year
    if args.quarter:  config["period"]["quarter"] = args.quarter
    if args.api_key:  config["dart"]["api_key"]   = args.api_key
    if args.companies:
        names = [n.strip() for n in args.companies.split(",")]
        config["companies"] = [
            c for c in config["companies"]
            if any(n in (c["short_name"], c["dart_name"]) for n in names)
        ]
    run(config)
