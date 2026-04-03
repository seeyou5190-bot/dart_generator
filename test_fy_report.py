#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import yaml

sys.path.insert(0, '.')

from dart_fetcher import DartFetcher

with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

fetcher = DartFetcher(config['dart']['api_key'])

# Test FY (quarter 4)
print("[TEST] 4분기 (연간 사업보고서) 검증")
print("=" * 60)

test_cases = [
    ('DB손해보험', 2024, 4),
    ('DB손해보험', 2025, 4),
]

for dart_name, year, quarter in test_cases:
    print(f"\n{dart_name} {year}년 {quarter}분기:")
    report = fetcher._find_report(dart_name, year, quarter)
    
    if report:
        print(f"  ✓ 보고서명: {report.get('report_nm')}")
        print(f"  ✓ 접수일: {report.get('rcept_dt')}")
    else:
        print(f"  ✗ 보고서 찾기 실패")
