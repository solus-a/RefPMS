# RefPMS 프로젝트 심층 분석 및 역설계 보고서 (Detailed Analysis & Reverse Engineering Report)

## 1. 개요 (Introduction)
본 보고서는 `RefPMS` 프로젝트의 현재 구현 상태를 정밀 분석하고, **5단계 계층 스키마(5-Layer Hierarchical Schema)**로의 진화 과정을 역설계(Reverse Engineering) 관점에서 정리합니다. 

## 2. 핵심 설계 원칙 및 의사결정 (Core Design Principles)
사용자와의 Q&A를 통해 확정된 핵심 아키텍처 방향입니다.

*   **L1: 단위 체계 (Unit System):** 프로젝트별 단일 단위(Inch 또는 Metric)를 원칙으로 함. 단, Tube류 등 혼합 규격은 **Size 필드의 다형성(Direction B: string | object)**을 통해 처리하며, `formatter.py`에서 렌더링을 담당함.
*   **L3: 아이템 코드 규칙:** 전사 표준 기반의 **'완전 고정 불변(Intelligent Code)'** 규칙을 적용함.
*   **L4: 원자적 속성 (Atomic Attributes):** 모든 부품군은 6개의 **Abstract Base Attributes**를 상속받음.
    1. `Item_Code`, 2. `Commodity_Group`, 3. `Primary_Size`, 4. `Base_Material_Category`, 5. `Short/Long_Description`, 6. `Remarks`
*   **데이터 출력:** 엔지니어링 검토용(부품군별 분리) 및 시스템 인터페이스용(Flat Data 통합)을 모두 지원함.

## 3. 부품군별 상세 원자 속성 정의 (Specific Atomic Attributes)
각 부품군이 가져야 할 L4 레벨의 상세 속성 리스트입니다. (상세 내용은 `plan.md` 및 원본 답변 참조)

*   **Pipe:** Material Spec/Grade, Method, Schedule, End Type 등
*   **Fitting:** 단일 `Size_From`/`Size_To`(Pipe와 동일), Material Spec/Grade, Schedule or Rating (XOR 적용) 등
*   **Flange:** Rating, Facing, Bore Schedule 등
*   **Gasket:** Type별 조건부 속성 (Winding, Filler, Inner/Outer Ring 등)
*   **Valve:** Trim Number(발주용) 및 상세 Trim 재질(3D/데이터용) 병렬 보유

## 4. 코드 및 데이터 구조 정밀 분석 (Current Implementation Analysis)

### 4.0 부품군 매핑·검증 (Phase 3)
*   **`data/component_mapping.json`**: 시트별 `required_non_empty`, `xor_at_most_one_filled`(예: Fitting `Schedule`/`Rating`), 확장용 `conditional_required`.
*   **`validator.py`**: 템플릿 행 단위 검증; 위반 시 로그 후 해당 행 출력 제외.

### 4.1 핵심 엔진: `pms_generator.py` 및 분리 모듈
*   **NPS Master:** `project_config.json`의 `nps_master.nps_list` 사용 (`thickness_engine.nps_list` / `explode_size_range`).
*   **Size Explosion:** `thickness_engine.explode_size_range` 및 `pms_generator`에서 L5(Atomic) 행 생성.
*   **Flange 설명:** `Bore_Schedule` 컬럼 없음; WN은 클래스 Schedule 룩업 두께(`sch1`)만 사용. 문구 순서: `{Item_Name 또는 FLANGE} {재질} {End_Type} {등급: CL150→150#} {Facing} [WN일 때 SCH] {Dim_Standard}`.
*   **Schedule 룩업:** `thickness_engine.load_schedule_rows`, `lookup_schedule_thickness` — NPS 리스트 매칭 후 **From~To 숫자 구간** 폴백.
*   **Reducing_Table:** `Item_Type` RD→RC/RE, SN→RCS/RES; **RC/RE/RCS/RES는 Fitting_Group 템플릿 행으로는 전개하지 않음**(중복 방지). **관례:** `Size1`(대단) > `Size2`(소단) — 동일·역전 NPS는 축관 개념과 맞지 않음. **RCS·RES 이음 표기:** `L`/`S`는 Large/Small 단면(NPS로 판별, `Size1`↔`End_Type_1`, `Size2`↔`End_Type_2`). 가운데 `B`는 Both — 양끝 종류가 같으면 `BBE`·`PBE`·`TBE` 등. 종류가 다르면 대단 `BLE`/`PLE`/…, 소단 `BSE`/`PSE`/… 조합(예: 대단 BE·소단 PE → `BLE/PSE` — 제작 시 어느 쪽이 BW/PE인지 명시). THD·미매핑 조합은 대·소단 원문 순으로 폴백. **설명 끝 규격:** RC/RE/RCS/RES는 `Dim_Standard`를 설명에 포함; **`Dim_Standard`에는 이음(BW 등)을 적지 않고** 규격명만(예: `ASME B16.9`, `MSS SP-95`). 잘못 `ASME B16.9 BW`로 들어온 구 템플릿만 코드에서 `ASME B16.9`로 정규화.
*   **Branch_Table:** `Class_Define.Branch_Table_1` → 테이블 코드; `Item_Type` **T**(등경)·**RT**(이경)만 전개. 클래스에 브랜치 테이블이 매핑되면 Fitting_Group 의 T/RT는 테이블 전용(리듀서와 동일 패턴). `Size1`/`Size2`는 Reducing_Table 과 같이 대단/소단 관례; RT 설명은 `fitting_dual_schedule` 로 대단·소단 스케줄 조합. 템플릿 행 선택은 NPS 구간 매칭 + `_branch_rt_template_reference_nps`·`_find_rt_fitting_template_row`(소단 SW·대단 BW 혼합 시 BW 행 우선).
*   **클래스 봉투:** `class_spec.load_class_specs_from_workbook`, `log_class_constraint_warnings`. 재질: `data/class_material_mapping.json` allowlist. Rating: B16.5 Class 집합 vs B16.11(3000# 등) 집합 **교차 비교 생략**.
*   **Description 생성:** 현재 문자열 결합 방식 -> Phase 4에서 원자 속성 기반 템플릿 방식으로 전환 예정.
*   **Item_Code_DB (`data/Item_Code_DB.xlsx`):** `Catalog_Item_Name` → PMS `Item_Name`; `Description_Prefix` → 설명 선두(레거시 `Item_Name` 단일 열은 둘 다 동일 값으로 로드). Pipe 니플(JN/JNP 계열): 길이는 `Length` 열만 사용, 카탈로그명 끝 `NNNmm` 을 길이로 치환해 발주명 정합.
*   **엘보 E/ES/E4/ES4:** B16.9(BW)는 LR/SR를 **설명**에 유지. B16.11은 ASME B16.11상 LR/SR 구분이 없어 **설명 선두**에서 LR/SR 제거. **Item_Name**은 B16.9·B16.11 공통으로 LR/SR 접미사 없이 `ELBOW 90 DEG`/`ELBOW 45 DEG` 형태로 통일.

---

## 5. 아키텍처적 결함 및 해결 방안 (Technical Debt & Solutions)
(기존 분석 내용 유지)
1. 속성 데이터의 비구조화 -> 원자적 데이터 필드로 분리.
2. 하드코딩된 마스터 데이터 -> `project_config.json` 도입.
3. 검증 로직 부재 -> Validator 모듈 구축.
4. 확장성 한계 -> `component_mapping.json` 도입.
5. B16.5/B16.11 등급 집합은 코드 상수(`class_spec`) — **사용 중 ASME 판본과 불일치 시 수정 필요**.

