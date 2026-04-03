#!/usr/bin/env python3
"""테스트: 4분기 검색 범위 확장 검증"""

import sys
import logging
from dart_fetcher import DartFetcher

logging.basicConfig(level=logging.INFO, format='%(message)s')

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python test_fy_full_range.py <DART_API_KEY>")
        sys.exit(1)
    
    dart_api_key = sys.argv[1]
    fetcher = DartFetcher(dart_api_key)
    
    print("\n[TEST] 4분기 (연간 사업보고서) - 확장 범위 검증")
    print("=" * 60)
    
    # 2025년 4분기 (2026년 접수)
    print("\n[1] DB손해보험 2025년 Q4 (예상: 2026년 접수)")
    report = fetcher._find_report("DB손해보험", 2025, 4)
    if report:
        print(f"  ✓ 보고서명: {report.get('report_nm', 'N/A')}")
        print(f"  ✓ 접수일: {report.get('rcept_dt', 'N/A')}")
        print(f"  ✓ 접수번호: {report.get('rcept_no', 'N/A')}")
    else:
        print("  ✗ 보고서를 찾지 못함")
    
    # 2024년 4분기 (검증용)
    print("\n[2] DB손해보험 2024년 Q4 (검증: 2025년 접수)")
    report = fetcher._find_report("DB손해보험", 2024, 4)
    if report:
        print(f"  ✓ 보고서명: {report.get('report_nm', 'N/A')}")
        print(f"  ✓ 접수일: {report.get('rcept_dt', 'N/A')}")
    else:
        print("  ✗ 보고서를 찾지 못함")
    
    print("\n" + "=" * 60)
