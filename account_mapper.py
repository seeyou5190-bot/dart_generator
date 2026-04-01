"""account_mapper.py - 계정과목 표준화 매핑 모듈"""

import re
import json
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class AccountMapper:
    SIMILARITY_AUTO_MATCH = 0.60   # 60% 이상이면 자동 매핑 (프롬프트 없음)
    SIMILARITY_ASK_USER   = 0.45   # 45~60%이면 사용자 확인 요청

    def __init__(self, account_config: list):
        self.standards = account_config
        self._cache: dict = {}
        self._user_decisions: dict = {}

    def map(self, raw_name: str, interactive: bool = True):
        key = self._normalize(raw_name)
        if key in self._cache:
            return self._cache[key]
        if key in self._user_decisions:
            result = self._user_decisions[key]
            self._cache[key] = result
            return result

        exact = self._exact_match(key)
        if exact:
            self._cache[key] = exact
            return exact

        best_std, score = self._best_similarity(key)

        if score >= self.SIMILARITY_AUTO_MATCH:
            logger.debug(f"자동 매핑 ({score:.0%}): {raw_name!r} → {best_std!r}")
            self._cache[key] = best_std
            return best_std

        # stdin이 실제 터미널인 경우에만 사용자 확인 요청
        import sys
        is_tty = interactive and hasattr(sys.stdin, 'isatty') and sys.stdin.isatty()
        if score >= self.SIMILARITY_ASK_USER and is_tty:
            result = self._ask_user(raw_name, best_std, score)
            self._user_decisions[key] = result
            self._cache[key] = result
            return result

        self._cache[key] = None
        return None

    def map_all(self, raw_names: list, interactive: bool = True) -> dict:
        return {name: self.map(name, interactive=interactive) for name in raw_names}

    def get_required_standards(self) -> list:
        return [acc["standard"] for acc in self.standards if acc.get("required")]

    def save_user_decisions(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._user_decisions, f, ensure_ascii=False, indent=2)

    def load_user_decisions(self, path: str):
        try:
            with open(path, encoding="utf-8") as f:
                self._user_decisions = json.load(f)
            logger.info(f"사용자 매핑 로드: {len(self._user_decisions)}건")
        except FileNotFoundError:
            pass

    @staticmethod
    def _normalize(name: str) -> str:
        name = re.sub(r"[（(].*?[)）]", "", name)
        name = re.sub(r"[\s\-·•※]", "", name)
        return name.strip()

    def _exact_match(self, key: str):
        for acc in self.standards:
            candidates = [self._normalize(acc["standard"])] +                                  [self._normalize(a) for a in acc.get("aliases", [])]
            if key in candidates:
                return acc["standard"]
        return None

    def _best_similarity(self, key: str):
        best_std, best_score = "", 0.0
        for acc in self.standards:
            candidates = [self._normalize(acc["standard"])] +                                  [self._normalize(a) for a in acc.get("aliases", [])]
            for cand in candidates:
                score = SequenceMatcher(None, key, cand).ratio()
                if score > best_score:
                    best_score = score
                    best_std = acc["standard"]
        return best_std, best_score

    @staticmethod
    def _ask_user(raw_name: str, suggested: str, score: float):
        print()
        print("=" * 60)
        print(f"  [계정과목 확인 필요]")
        print(f"  원본 계정명 : {raw_name}")
        print(f"  추천 표준명 : {suggested}  (유사도 {score:.0%})")
        print("=" * 60)
        print("  [1] 추천 표준명으로 매핑")
        print("  [2] 매핑하지 않음 (스킵)")
        print("  [3] 직접 입력")
        while True:
            try:
                choice = input("  입력 (1/2/3): ").strip()
            except EOFError:
                # 파이프라인/백그라운드 실행 등 stdin이 없을 때는 스킵
                return None

            if choice == "1":
                return suggested
            elif choice == "2":
                return None
            elif choice == "3":
                custom = input("  표준 계정명 직접 입력: ").strip()
                if custom:
                    return custom
