# DART Generator 계정과목 추가 가이드

## 1. 재무상태표(Balance Sheet) 계정과목 추가

### 위치
`config.yaml`에서 `balance_sheet_accounts` 섹션

### 현재 구조 예시
```yaml
balance_sheet_accounts:
  - standard: "자산 총계"
    aliases: ["자산총계", "총자산", "자산합계", "합계"]
    required: true
  - standard: "현금및현금성자산"
    aliases: ["현금및현금등가물", "현금및예치금", "현금성자산"]
    required: false
  # ... 더 많은 항목들
```

### 추가 방법
1. 추가하고 싶은 계정과목을 리스트에 추가합니다
2. `standard`: 표준화된 계정명 (필수)
3. `aliases`: 원본 데이터에서 나올 수 있는 다양한 표현들 (배열, 선택사항)
4. `required`: 필수 항목 여부 (true/false, 선택사항)

### 예시: "투자자산" 추가
```yaml
  - standard: "투자자산"
    aliases: ["투자자산합계", "유가증권", "금융자산"]
    required: false
```

---

## 2. 손익계산서(Income Statement) 계정과목 추가

### 위치
`config.yaml`에서 `income_statement_accounts` 섹션

### 현재 구조 예시
```yaml
income_statement_accounts:
  - standard: "보험료수익"
    aliases: ["원수보험료", "보험료", "수입보험료", "보험수익"]
    required: true
  - standard: "보험금비용"
    aliases: ["보험금", "지급보험금", "보험비용"]
    required: true
  # ... 더 많은 항목들
```

### 추가 방법
재무상태표와 동일한 방식입니다.

### 예시: "이자수익" 추가
```yaml
  - standard: "이자수익"
    aliases: ["이자소득", "이자수익금"]
    required: false
```

---

## 3. 반영되는 위치

추가한 계정과목은 다음과 같이 반영됩니다:

### 엑셀 파일 개별 회사 시트
- **재무상태표** 섹션에 `balance_sheet_accounts`의 항목들이 표시됩니다
- **손익계산서** 섹션에 `income_statement_accounts`의 항목들이 표시됩니다

### 엑셀 파일 손보사 비교 시트
- 왼쪽에 모든 계정과목이 표시됩니다
- 각 회사의 데이터가 옆에 나열됩니다

---

## 4. 주의사항

1. **순서**: 리스트에 추가한 순서대로 엑셀에 표시됩니다
2. **Aliases**: DART에서 추출한 원본 계정명과 매칭됩니다. 최대한 다양하게 추가하세요
3. **YAML 문법**: 들여쓰기는 반드시 2칸 또는 4칸 일관성있게 해야 합니다
4. **저장**: config.yaml 수정 후 서버 재시작 필요

---

## 5. 예시: 전체 추가 예

```yaml
balance_sheet_accounts:
  - standard: "자산 총계"
    aliases: ["자산총계", "총자산"]
    required: true
  - standard: "현금및현금성자산"
    aliases: ["현금및현금등가물"]
    required: false
  - standard: "투자자산"          # 새로 추가
    aliases: ["투자자산합계", "유가증권"]
    required: false
  - standard: "부채 총계"
    aliases: ["부채총계", "총부채"]
    required: true

income_statement_accounts:
  - standard: "보험료수익"
    aliases: ["원수보험료"]
    required: true
  - standard: "이자수익"          # 새로 추가
    aliases: ["이자소득"]
    required: false
  - standard: "당기순이익"
    aliases: ["순이익"]
    required: true
```

---

## 6. 적용 순서

1. `config.yaml` 수정
2. 서버 재시작 (`uvicorn app:app --reload` 또는 Render 재배포)
3. 웹에서 "🚀 재무제표 수집 실행" 클릭
4. 엑셀 다운로드 후 확인

문제가 있으면 로그에서 매핑 메시지를 확인하세요!
