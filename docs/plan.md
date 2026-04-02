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

## Phase 2: Layer 2 - Class/Spec Technical Envelope (Next)
**Goal:** 엔지니어링 제약 조건 및 두께/Rating 룩업 테이블 정형화.

### Key Tasks:
1. **`ClassSpec` 모델 구현**: Design Code, P/T Rating, Corrosion Allowance 등 관리.
2. **`ThicknessEngine` 고도화**: 사이즈별 스케줄 매핑 및 보간 규칙 적용.
3. **제약 조건 검증**: 부품군(L4)이 클래스의 Rating 및 재질 제한을 준수하는지 체크.

---

## Phase 3: Layer 3 - Group Logic Generalization
**Goal:** 부품군별 속성 매핑을 설정화하여 엔진을 범용화.

### Key Tasks:
1. **`component_mapping.json` 생성**:
    - 부품군별 필수/선택 속성 정의.
    - **Gasket 서브타입 로직**: Gasket_Type에 따른 조건부 속성 활성화.
    - **Fitting XOR 로직**: Schedule vs Rating 배타적 선택 처리.
2. **Dynamic Validator**: 각 레코드가 부품군별 필수 속성을 갖추었는지 검증.

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
