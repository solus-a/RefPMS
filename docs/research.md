# RefPMS 프로젝트 심층 분석 및 역설계 보고서 (Detailed Analysis & Reverse Engineering Report)

## 1. 개요 (Introduction)
본 보고서는 `RefPMS` 프로젝트의 현재 구현 상태를 정밀 분석하고, `PROJECT_HISTORY.md`에서 정의된 **5단계 계층 스키마(5-Layer Hierarchical Schema)**로의 진화 과정을 역설계(Reverse Engineering) 관점에서 정리합니다. 

이 프로젝트는 초기 구현(`.py`, `.xlsx`)이 진행된 후, 시스템의 확장성과 범용성을 위해 아키텍처를 재정립한 특징을 가지고 있습니다. 따라서 현재 코드는 새로운 설계 철학을 구현해가는 "과도기적 상태"에 있습니다.

---

## 2. 코드 및 데이터 구조 정밀 분석 (Current Implementation Analysis)

### 2.1 핵심 엔진: `pms_generator.py`
이 파일은 프로젝트의 "심장"으로, 정적인 엑셀 데이터를 동적인 엔지니어링 데이터로 변환하는 비즈니스 로직이 집중되어 있습니다.

*   **NPS Master (Layer 1의 초기 형태):** `NPS_LIST`라는 상수로 하드코딩된 사이즈 리스트는 모든 사이즈 확장 로직의 기준점입니다. 
*   **Size Explosion 로직:** `_explode_size_range` 함수는 사용자의 "범위 입력"을 "개별 사이즈"로 파편화합니다. 이는 Layer 5(Atomic Layer)를 생성하는 핵심 메커니즘입니다.
*   **Schedule Lookup 로직:** `_lookup_schedule_thickness` 함수는 Layer 2(Class Layer)의 기술적 제약 조건을 실제 데이터에 주입합니다. 클래스와 사이즈를 기준으로 두께를 결정하는 2차원 매핑을 수행합니다.
*   **Description 규칙 기반 생성 (Layer 4의 초기 형태):** `_build_item_description_by_rule` 함수는 부품군별로 서로 다른 속성 조합 규칙을 가집니다. 현재는 속성을 문자열로 결합(String Concatenation)하는 방식입니다.

### 2.2 템플릿 구조: `template_generator.py`
입력 데이터의 규격(Schema)을 정의하며, 사용자가 엔지니어링 의도(Intent)를 입력하는 인터페이스 역할을 합니다.

*   **시트 구성:** `Class_Define`, `Schedule`, `Reducing_Table`, `Pipe_Group`, `Fitting_Group`, `Flange`, `Valve` 등 총 9개의 시트로 구성되어 데이터의 정규화를 유도합니다.
*   **Reducing Table 분화 로직:** 단순한 1:1 변환이 아니라, `RD(Reducer)`나 `SN(Swage)`과 같은 대표 코드를 `RC/RE`, `RCS/RES`와 같은 물리적 실체로 분화시키는 고차원 로직이 포함되어 있습니다.

### 2.3 데이터 자산: `Item_Code_DB.xlsx`
*   프로젝트 외부에서 관리되는 마스터 데이터로, 각 `Item_Code`의 표준 명칭(`Item_Name`)과 그룹 분류(`Group`)를 제공합니다. 이는 Layer 3(Group Layer)의 토대가 됩니다.

---

## 3. 5단계 계층 스키마와의 정렬 상태 (Alignment with 5-Layer Schema)

현재 구현된 코드와 `PROJECT_HISTORY.md`의 설계 철학을 대조한 결과입니다.

| 계층 (Layer) | 현재 구현 방식 (Implementation) | 설계 철학과의 일치도 및 과제 |
| :--- | :--- | :--- |
| **L1: Project** | `pms_generator.py` 내의 `NPS_LIST` 상수 | **과제:** 하드코딩된 리스트를 프로젝트별 설정 파일로 외부화 필요. |
| **L2: Class** | 템플릿의 `Class_Define` 및 `Schedule` 시트 | **일치:** 클래스별 엔지니어링 제약 조건을 잘 담고 있음. |
| **L3: Group** | `Item_Code_DB` 및 `MATERIAL_SHEET_CONFIGS` | **일치:** 부품군별 속성 분리가 이미 코드 레벨에서 이루어짐. |
| **L4: Definition** | `_build_item_description_by_rule` 함수 | **과제:** 문자열 결합 방식에서 "Atomic Attribute" 개별 저장 방식으로 전환 필요. |
| **L5: Atomic** | 최종 출력되는 Excel 행 데이터 | **일치:** 엔진에 의해 생성된 최종 결과물로서의 역할 수행 중. |

---

## 4. 아키텍처적 결함 및 해결 방안 (Technical Debt & Solutions)

1.  **속성 데이터의 비구조화 (Unstructured Attributes)**
    *   **문제:** `Item_Description`이 단순 문자열로 결합되어 있어 재활용 및 데이터 정규화가 어려움.
    *   **해결:** Layer 4(Definition Layer)에서 모든 속성을 원자적 데이터(Material, Grade, Schedule 등)로 분리하여 저장하고, 최종 문자열은 이 데이터들을 기반으로 템플릿 엔진이 생성하도록 구조 변경.

2.  **하드코딩된 마스터 데이터 (Hardcoded Master Data)**
    *   **문제:** `NPS_LIST` 등 프로젝트 핵심 규칙이 코드 내부에 고정되어 프로젝트 간 전용이 어려움.
    *   **해결:** `project_config.json`을 도입하여 프로젝트별 단위(Unit), 사이즈 리스트, 코딩 규칙을 외부 설정으로 관리.

3.  **검증 로직의 부재 (Lack of Validation)**
    *   **문제:** 잘못된 조합(NPS-Schedule 누락 등)이나 데이터 무결성 체크가 사후에 발견됨.
    *   **해결:** 데이터 생성 전 단계에서 Layer 2(Class Spec)와 Layer 3(Group Rule)에 정의된 제약 조건을 전수 검증하는 Validator 모듈 구축.

4.  **확장성 한계 (Extensibility Limits)**
    *   **문제:** 새로운 부품군 추가 시 하드코딩된 조건문을 대대적으로 수정해야 함.
    *   **해결:** `component_mapping.json`을 통해 부품군별 필요 속성을 정의하는 "메타데이터 기반 매핑" 엔진 도입. 로직 수정 없이 설정 추가만으로 새로운 부품 대응 가능.

---

## 5. 결론 및 향후 기획 방향 (Conclusion & Next Steps)

현재 `RefPMS`는 초기 구현을 통해 **"데이터 확장 및 변환"**이라는 핵심 기능을 성공적으로 증명했습니다. 이제 `PROJECT_HISTORY.md`의 비전에 따라 다음 단계로 나아가야 합니다.

1.  **속성의 원자화 (Atomization):** `Item_Description`을 만드는 중간 단계에서 모든 속성(Material, Grade, Schedule, Rating 등)을 개별 데이터 필드로 유지하는 구조로 전환합니다.
2.  **설정의 외부화 (Configuration):** Layer 1의 규칙(단위, 사이즈 리스트 등)을 프로젝트 루트의 별도 설정 파일로 분리합니다.
3.  **엔진의 범용화:** 특정 부품군에 종속되지 않는 범용 속성 매핑 엔진으로 고도화하여 Layer 4의 "Engineering DNA"를 완벽히 구현합니다.
