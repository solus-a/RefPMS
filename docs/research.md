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
*   **Fitting:** Size1/2, Material Spec/Grade, Schedule or Rating (XOR 적용) 등
*   **Flange:** Rating, Facing, Bore Schedule 등
*   **Gasket:** Type별 조건부 속성 (Winding, Filler, Inner/Outer Ring 등)
*   **Valve:** Trim Number(발주용) 및 상세 Trim 재질(3D/데이터용) 병렬 보유

## 4. 코드 및 데이터 구조 정밀 분석 (Current Implementation Analysis)

### 4.1 핵심 엔진: `pms_generator.py` 및 분리 모듈
*   **NPS Master:** `project_config.json`의 `nps_master.nps_list` 사용 (`thickness_engine.nps_list` / `explode_size_range`).
*   **Size Explosion:** `thickness_engine.explode_size_range` 및 `pms_generator`에서 L5(Atomic) 행 생성.
*   **Schedule 룩업:** `thickness_engine.load_schedule_rows`, `lookup_schedule_thickness` — NPS 리스트 매칭 후 **From~To 숫자 구간** 폴백.
*   **Reducing_Table:** `Item_Type` RD→RC/RE, SN→RCS/RES; **RC/RE/RCS/RES는 Fitting_Group 템플릿 행으로는 전개하지 않음**(중복 방지). RCS·RES 설명: BE+PE일 때 스케줄 동일 `PBE`, 상이 `BLE/PSE`.
*   **클래스 봉투:** `class_spec.load_class_specs_from_workbook`, `log_class_constraint_warnings`. 재질: `data/class_material_mapping.json` allowlist. Rating: B16.5 Class 집합 vs B16.11(3000# 등) 집합 **교차 비교 생략**.
*   **Description 생성:** 현재 문자열 결합 방식 -> Phase 4에서 원자 속성 기반 템플릿 방식으로 전환 예정.

---

## 5. 아키텍처적 결함 및 해결 방안 (Technical Debt & Solutions)
(기존 분석 내용 유지)
1. 속성 데이터의 비구조화 -> 원자적 데이터 필드로 분리.
2. 하드코딩된 마스터 데이터 -> `project_config.json` 도입.
3. 검증 로직 부재 -> Validator 모듈 구축.
4. 확장성 한계 -> `component_mapping.json` 도입.
5. B16.5/B16.11 등급 집합은 코드 상수(`class_spec`) — **사용 중 ASME 판본과 불일치 시 수정 필요**.

