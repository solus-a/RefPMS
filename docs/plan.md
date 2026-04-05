# RefPMS: Universal Data Engine Completion Plan (Updated)

이 문서는 사용자의 답변을 반영하여 RefPMS를 **5단계 계층 스키마** 기반의 데이터 엔진으로 완성하기 위한 로드맵입니다.

---

## Phase 1: Layer 1 - Project Context Externalization (Completed)
**Goal:** 하드코딩된 상수를 제거하고 프로젝트별 "물리 법칙"을 설정 파일로 관리.

### Key Tasks:
1. [x] **`project_config.json` 설계 및 생성**:
    - `unit_system`: "Inch" 또는 "Metric" (Direction B 적용).
    - `NPS_LIST`: 프로젝트에서 유효한 사이즈 리스트.
    - `coding_rules`: Commodity Code 생성 규칙 (고정형).
2. [x] **`config.py` 로더 구현**: JSON 설정을 로드하여 전역에서 접근 가능하도록 수정.
3. [x] **`pms_generator.py` 상수 치환**: `NPS_LIST` 등을 설정 파일 참조로 리팩토링.

---

## Phase 2: Layer 2 - Class/Spec Technical Envelope (Baseline done)
**Goal:** 엔지니어링 제약 조건 및 두께/Rating 룩업 테이블 정형화.

### Key Tasks:
1. [x] **`ClassSpec` 모델 구현**: `class_spec.py` — `Class_Define` 시트에서 Design Code, Class_Rating, Corrosion Allowance, P/T 범위 등 로드 (`TypedDict`).
2. [x] **`ThicknessEngine` 정형화**: `thickness_engine.py` — Schedule 시트 룩업, `project_config.json`의 `nps_master`; 행 전개는 NPS 리스트 연속 구간, **Schedule 룩업**은 From~To **숫자 구간** 폴백(Reducing 등 nps_list에 없는 NPS).
3. [x] **제약 조건 검증(1차)**: `log_class_constraint_warnings` — `Class_Rating` vs 부품 `Rating`(ASME **B16.5 P-T Class** vs **B16.11** 단조 등급은 교차 비교 안 함), 재질은 **`data/class_material_mapping.json`** allowlist(키=Class_Base_Material). 경고만, 행 스킵 없음.
4. [x] **출력 규칙 정합**: RC/RE/RCS/RES는 `Reducing_Table`에서만 전개; RCS·RES 이음은 NPS 대·소(L/S) 및 양끝 동일 시 BBE/PBE/TBE 등(`_rcs_res_end_type_token`).

---

## Phase 3: Layer 3 - Group Logic Generalization
**Goal:** 부품군별 속성 매핑을 설정화하여 엔진을 범용화.

### Key Tasks:
1. [x] **`component_mapping.json` 생성** (`data/component_mapping.json`):
    - 부품군별 필수 속성(`required_non_empty`) — Pipe / Fitting / Flange / Valve.
    - **Fitting XOR**: 동일 행에 `Schedule`·`Rating` 컬럼이 둘 다 있으면 둘 다 채우지 않음 (`xor_at_most_one_filled`).
    - **Gasket**: `Gasket_Group` 플레이스홀더 + `conditional_required`는 템플릿·허용 값 확정 후 편집.
2. [x] **Dynamic Validator** (`src/validator.py`): `validate_template_row` — 위 규칙 위반 시 경고 로그 후 해당 템플릿 행 스킵 (`pms_generator._iter_output_rows` 연동).
3. [x] **Item_Code DB 스키마·사이드카:** `Catalog_Item_Name` / `Description_Prefix` 열, 템플릿·PMS 실행 시 `ensure_all_program_data_files()` 로 JSON·DB 보장 및 레거시 시트 정규화.
4. [x] **Branch_Table:** `Branch_Table` 시트·`Class_Define.Branch_Table_1` 로 T/RT 분기 전개 (`pms_generator`).

---

## Phase 4: Layer 4 - Attribute Atomization (Engineering DNA)
**Goal:** 설명을 문자열이 아닌 구조화된 원자 데이터로 관리.

### Key Tasks:
1. **Abstract Base Attributes 상속 구조**:
    - 6대 공통 속성 (`Item_Code`, `Group`, `Size`, `Base_Mat`, `Desc`, `Remarks`) 필수 구현.
2. **부품군별 원자 속성 전개**:
    - Valve Trim의 이중 관리 (Trim No. + 개별 재질).
    - Size 필드의 다형성 처리 (Mixed Unit 대응).
3. **Rule-Based Generator (`formatter.py`)**: 원자 속성을 조합하여 Short/Long Description 자동 생성.

---

## Phase 5: Layer 5 - Atomic Generation & Export
**Goal:** 최종 데이터 확정 및 다중 포맷 출력.

### Key Tasks:
1. **Flat Data 통합 출력**: 프로젝트 전체 데이터를 하나의 시트로 통합하는 기능 추가.
2. **부품군별 분리 출력 유지**: 기존 엔지니어링 검토용 포맷 지원.
3. **GUI 업데이트**: 진행률 표시 및 유효성 검사 리포트 뷰 추가.

---

## Success Criteria (Updated)
- [x] 프로젝트 단위 체계 설정 지원 (Mixed Unit 예외 포함).
- [x] 전사 표준 기반의 고정 아이템 코드 규칙 적용.
- [x] 원자적 속성 기반의 데이터 구조 (Description 자동 생성).
- [x] 부품군별 분리 및 통합 출력 동시 지원.
