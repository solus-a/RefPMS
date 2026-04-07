# RefPMS 아키텍처/설계 정리 (Research)

본 문서는 현재 구현의 설계 의도와 기술 선택을 설명합니다.
진행 이력은 `docs/progress.md`, 일정/우선순위는 `docs/plan.md`를 기준으로 합니다.

---

## 1) 핵심 설계 원칙

- **설정 주도형 엔진:** 프로젝트별 규칙은 가능한 `project_config.json`과 데이터 파일로 외부화
- **룰 기반 검증:** 템플릿 행은 `component_mapping` 규칙으로 검사하고 위반 시 스킵/경고
- **산출물 정합 우선:** 현재 단계에서는 코드 스타일보다 결과값 일치가 우선
- **점진적 진화:** 문자열 조합 중심(현재)에서 원자 속성 중심(Phase 4)으로 전환

---

## 2) 현재 구현 구조

### 2.1 입력/검증 계층

- `src/validator.py`
  - `required_non_empty`
  - `xor_at_most_one_filled` (예: Fitting `Schedule`/`Rating`)
  - `conditional_required` (예: Gasket 타입별 필수 컬럼)
- `data/component_mapping.json`
  - 시트별 검증 규칙 정의의 단일 소스

### 2.2 생성 계층 (`src/pms_generator.py`)

- 공통 흐름
  - 시트 로드 -> 행 검증 -> 사이즈 전개 -> 두께 룩업/선택 -> 설명/품목명 조합 -> 정렬/출력
- 주요 시트
  - `Pipe_Group`, `Fitting_Group`, `Flange_Group`, `Gasket_Group`, `Valve`
- 테이블 전개
  - `Reducing_Table`: RD/SN -> RC/RE/RCS/RES 매핑
  - `Branch_Table`: T/RT/TH 분기 전개

### 2.3 데이터/보조 파일 계층

- `src/template_generator.py`
  - 템플릿 시트/헤더 생성
  - JSON/DB 사이드카 보장 (`ensure_all_program_data_files`)
- `data/Item_Code_DB.xlsx`
  - `Catalog_Item_Name`, `Description_Prefix`, `Group` 기준으로 설명/품목명 조합

---

## 3) 시트별 핵심 규칙 요약

### 3.1 Flange_Group

- 타입 입력은 `Flange_Type` 우선 (`End_Type` 폴백)
- 설명의 SCH 토큰은 SW/WN일 때만 포함
- 등급 표시는 `CL150 -> 150#` 변환

### 3.2 Gasket_Group

- 설명 토큰 순서:
  - `Gasket_Type` + 재질 조합 + `IR-/OR-` + `Rating` + `Facing` + `Thickness` + `Remarks` + `Dim_Standard`
- `Thickness1`은 `Schedule` 룩업이 아니라 입력 `Thickness`를 그대로 사용
- `conditional_required`는 타입별 필수값 강제

### 3.3 Fitting_Group (요약)

- 리듀서/스웨이지는 `Reducing_Table` 기반 전개로 중복 방지
- RT/TH는 `Branch_Table` 규칙에 따라 전개
- Thread 표기는 `project_info.thread_method`(현재 `NPT`) 기준

---

## 4) 자동화 검증 하네스

### 4.1 목적

- 수동 엑셀 대조를 줄이고, 결과값 기준 Pass/Fail 자동 판정

### 4.2 구성

- 입력: `tests/input/<case>/Class_Define_Template.xlsx`
- 기대결과: `tests/expected/<case>/Piping_Material_Class_Data.xlsx`
- 실행기:
  - `python -m tests.harness_runner --all`
  - `python -m tests.harness_runner --case <name>`
  - `python run.py harness ...`

### 4.3 판정

- 시트명, 행 수, 셀값 비교
- 종료코드:
  - 성공 `0`
  - 실패 `1`
  - 사용 오류 `2`

---

## 5) 기술 부채 / 다음 연구 주제

1. **설명 문자열의 비구조화**  
   -> Phase 4에서 원자 속성 + formatter 계층으로 전환
2. **룰 파일 확장성**  
   -> 도메인 규칙 증가 시 스키마 버전 전략 필요
3. **검증 커버리지 확대**  
   -> 하네스 실케이스(정상/오류/경계) 추가 필요
4. **규격 집합 유지보수**  
   -> B16.5/B16.11 기준값의 판본 동기화 관리 필요

---

*Last Updated: 2026-04-07*

