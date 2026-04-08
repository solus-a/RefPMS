# RefPMS 아키텍처/설계 정리 (Research)

설계 의도·모듈·시트 규칙 요약입니다. **운영 불변 규칙·스택·금지 사항**은 `.cursor/rules/refpms-context.mdc`를 단일 참조로 둡니다.

일정·Phase는 `docs/plan.md`, 짧은 변경 이력은 `docs/changelog.md`입니다.

---

## 1) 핵심 설계 원칙

- **설정 주도형 엔진:** `project_config.json`과 데이터 파일로 외부화
- **룰 기반 검증:** `data/component_mapping.json` + `src/validator.py` — 위반 시 스킵/경고
- **산출물 정합 우선:** 결과값 일치·하네스 회귀가 우선
- **점진적 진화:** 문자열 조합(현재) → 원자 속성 + formatter(Phase 4)

---

## 2) 현재 구현 구조

### 2.1 입력/검증 계층

- `src/validator.py` — `required_non_empty`, `xor_at_most_one_filled`, `conditional_required`
- `data/component_mapping.json` — 시트별 검증 규칙 SSOT

### 2.2 생성 계층 (`src/pms_generator.py`)

- 흐름: 시트 로드 → 행 검증 → 사이즈 전개 → 두께 룩업 → 설명/품목명 → 정렬/출력
- 시트: `Pipe_Group`, `Fitting_Group`, `Flange_Group`, `Gasket_Group`, `Valve`
- 테이블 전개: `Reducing_Table`(RD/SN), `Branch_Table`(T/RT/TH)

### 2.3 데이터/보조

- `src/template_generator.py` — 템플릿·`Item_Code_DB` 보조
- `data/Item_Code_DB.xlsx` — 카탈로그명·설명 접두·Group

---

## 3) 시트별 핵심 규칙 요약

### 3.1 Flange_Group

- `Flange_Type` 우선 (`End_Type` 폴백), SCH는 SW/WN만, `CL150` → `150#`

### 3.2 Gasket_Group

- 설명 순서: 타입 → 재질·IR/OR → Rating → Facing → Thickness → Remarks → Dim_Standard
- `Thickness1`은 Schedule이 아니라 입력 `Thickness` 그대로

### 3.3 Fitting_Group

- 리듀서/스웨이지: `Reducing_Table` 전개로 템플릿 중복 방지
- RT/TH: `Branch_Table` 규칙, 스레드는 `project_info.thread_method`

---

## 4) 자동화 검증 하네스

Golden 비교: `tests/input/<case>/` ↔ `tests/expected/<case>/`. 실행·종료코드는 `tests/README.md` 및 `tests/harness_runner.py` 참고.

---

## 5) 기술 부채 / 다음 연구 주제

1. 설명 문자열 비구조화 → Phase 4 원자 속성 + formatter
2. 룰 파일 스키마 버전 전략
3. 하네스 케이스(정상/경계) 확대
4. 규격 판본 동기화 관리

---

*Last Updated: 2026-04-08*
