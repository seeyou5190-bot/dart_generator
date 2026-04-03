#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import yaml
import pandas as pd

sys.path.insert(0, '.')

from dart_fetcher import DartFetcher

with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

fetcher = DartFetcher(config['dart']['api_key'])

# DART API에서 반환되는 모든 컬럼 확인
dart_name = 'DB손해보험'
year = 2025

df = fetcher.dart.list(dart_name, start=f"{year}0101", end=f"{year}1231", kind="A")

if df is not None and not df.empty:
    print(f"[DART API 컬럼 정보]")
    print(f"Columns: {list(df.columns)}")
    print(f"\n[사업보고서 샘플 데이터]")
    
    mask = df["report_nm"].str.contains("사업보고서", na=False)
    filtered = df[mask].sort_values('rcept_dt', ascending=False)
    
    if not filtered.empty:
        row = filtered.iloc[0]
        print(f"\n최신 사업보고서:")
        for col in df.columns:
            val = row.get(col)
            if pd.notna(val):
                print(f"  {col}: {val}")
