# Project Progress Report

## 세션 요약 (2026-04-05, Item_Code DB·니플)

- **Item_Code_DB.xlsx:** `Catalog_Item_Name`(출력 `Item_Name`), `Description_Prefix`(설명 선두), 레거시 `Item_Name` 단일 열은 로드 시 카탈로그·접두 동일 처리. `template_generator.ensure_item_code_db` 가 누락 열이면 시트를 표준 4열로 재배치 후 기본 코드 행 병합.
- **JSON 사이드카:** `ensure_all_program_data_files()` — `class_material_mapping.json` / `component_mapping.json` 없으면 기본 생성; 템플릿 생성·PMS 생성 전에 호출.
- **니플(Pipe_Group JN/JNP 계열):** 길이는 `Length` 열만 사용(Remarks 에서 길이 폴백 없음). `Item_Name` 은 DB 카탈로그명 끝 `NNNmm` 를 길이 값으로 치환·특수 조건은 Remarks 를 설명·출력 Remarks 에 반영.
- **JNT / JNT1 (TE/TE):** 설명·발주명은 `TBE` 토큰·DB 카탈로그 `NIPPLE (TBE) 75mm`/`100mm`. 출력 정렬: `project_config.json` `item_order` 에 `JNT`·`JNT1` 포함(P → JN → JNP → JNT → JN1 → JNP1 → JNT1 …). 카탈로그 끝 `mm` 가 Length 와 동일할 때 `75mm 75mm` 중복 없음.
- **검증:** `template/20260405_142914/Class_Define_Template.xlsx` → 생성 결과가 `output/20260405_143053/Piping_Material_Class_Data.xlsx` 과 행·셀 일치(스모크).
- **엘보 LR/SR:** ASME **B16.11**(단조·SW 등) 행은 `Dim_Standard`에 B16.11이면 `Item_Description` 선두에서 LR/SR 제거. **Item_Name**은 E/ES/E4/ES4 전 구간에서 LR/SR 접미사 제거(발주명은 `ELBOW 90 DEG`/`ELBOW 45 DEG`); B16.9 BW 행은 설명에만 LR·SR 유지. 기준 출력: `output/20260405_150349/Piping_Material_Class_Data.xlsx`.
- **리듀서·스웨이지 설명:** RC/RE/RCS/RES 분기에서 `Dim_Standard`를 설명 끝에 포함(예: `ASME B16.9`, `MSS SP-95`). **`Dim_Standard`에는 BW 등 이음을 넣지 않음** — 이음은 `End_Type` 쪽에서만. 레거시로 `ASME B16.9 BW`가 들어온 경우만 `_reducer_description_dim_standard`에서 `ASME B16.9`로 정리. Reducing_Table·축관은 **대단 NPS > 소단 NPS** 관례; RCS/RES 혼합 이음은 `BLE/PSE` 등(기존 `_rcs_res_end_type_token`). 기준 출력: `output/20260405_152040/Piping_Material_Class_Data.xlsx`.
- **Branch_Table:** `Class_Define.Branch_Table_1` → 테이블 코드; 시트 `Branch_Table`(헤더 Reducing_Table 과 동일). `Item_Type` **T**=등경 티, **RT**=이경 티 → `Fitting_Group` 의 T/RT 템플릿으로 전개(클래스에 브랜치 테이블이 있으면 T/RT 템플릿 행은 중복 전개 안 함). RT 템플릿 행은 `_branch_rt_template_reference_nps`·`_find_rt_fitting_template_row`(소단 SW·대단 BW 혼합 시 BW 행 우선). **22″×10″ RT**는 22″×12″ 등과 동일하게 소단 기준 SMLS 템플릿·Schedule 두께(STD×SCH40)만 사용(잘못된 예외 보정 제거). 출력 정렬: `T`/`RT` 는 Size2 숫자 순, 그 외는 Size2 문자열 순. `project_config.json` `item_order` 에 `T`,`RT` 추가. 신규 템플릿에 `Branch_Table` 시트 생성(`template_generator`).
- **저장소 정책:** 로컬 비교·실험 산출물 `build-output/`와 워크스페이스 `.vscode/`(에디터 전용)는 `.gitignore`에 두고 Git에 올리지 않음.

## 세션 요약 (2026-04-05)

- **GUI 출력 폴더 타임스탬프:** 형식 `YYYYMMDD_HHMMSS` — `controller` 템플릿·자재 클래스 생성 경로.
- **템플릿 컬럼:** `Fitting_Group` — `Size1/Size2_*` 제거, `Size_From`/`Size_To`만(Pipe와 동일). `Flange` — `Bore_Schedule` 제거; 생성기 Flange 설명은 WN일 때 스케줄 룩업 두께만 사용.
- **출력 설명:** Flange `_flange_rating_display` 등. RCS·RES: NPS 대·소에 따른 L/S 토큰, 양끝 동일 타입 시 BBE/PBE/TBE(`_rcs_res_end_type_token`).
- **Phase 3 착수:** `data/component_mapping.json`(시트별 필수 필드, Fitting `Schedule`/`Rating` 배타), `src/validator.py`(`load_component_mapping`, `validate_template_row`), `config.component_mapping_path()`.
- **연동:** `pms_generator._iter_output_rows`에서 행 단위 검증 — 실패 시 경고 후 스킵; Reducing_Table 전개 시에도 해당 Fitting 템플릿 행 검증.
- **스모크:** 빈 템플릿 생성 → PMS 출력까지 통과.
- **다음:** Gasket 시트·`conditional_required` 실값 반영, `dropdown_values.xlsx` 연동(승인된 값만), Phase 4 원자 속성.

## 세션 마감 요약 (2026-04-04)

- **코드:** `excel_sheet_utils`, `thickness_engine`, `class_spec`, `pms_generator` 리팩터·동작 정합; `controller` 출력 경로 `template/`·`output/` + `YYYYMMDD_HHMMSS`.
- **데이터:** `data/class_material_mapping.json`(재질 allowlist), `project_config.json` NPS/출력 설정.
- **검증:** 템플릿·PMS 생성 스모크 통과.
- **규칙:** `.cursor/rules/docs-workflow.mdc`, `folder-naming.mdc`.
- **다음:** Phase 3 나머지(Gasket 조건·드롭다운) 또는 Phase 4/5.

## 2026-04-02: Phase 1 Completion & Infrastructure Setup

### **1. Phase 1: Layer 1 - Project Context Externalization**
- **목적:** 코드 내 하드코딩된 엔지니어링 상수를 외부 설정으로 분리하여 프로젝트별 범용성 확보.
- **상세 작업 내용:**
    - `project_config.json` 설계: `unit_system`, `nps_master`, `output_settings`, `coding_rules` 정의.
    - `src/config.py` 고도화: 
        - `ProjectConfig` 싱글톤 클래스 구현.
        - 점 표기법(Dot notation)을 통한 설정값 접근 기능(`get` 메서드) 추가.
    - `src/pms_generator.py` 리팩토링:
        - `NPS_LIST`, `OUTPUT_COLUMNS`, `ITEM_CODE_OUTPUT_ORDER` 등 상수를 `config_manager` 호출로 대체.
- **결과:** 코드 수정 없이 JSON 파일 변경만으로 프로젝트의 물리 법칙(사이즈 리스트, 단위 등)을 정의할 수 있는 기반 마련.

### **2. Documentation & System Integrity**
- **문서 통합:** `research.md`와 `plan.md`에 사용자 답변 및 상세 속성 정의를 반영하여 최신화.
- **전역 지침 설정:** `save_memory`를 통해 모든 세션에서 "실행 전 문서 분석 우선" 규칙을 강제함.
- **진행 관리:** `Progress.md`와 `docs/chat/` 기록 체계를 구축하여 작업 투명성 및 연속성 확보.

### **3. Current Status** (롤링 요약)
- **Current Phase:** Phase 2 baseline 완료 (위 세션 마감 요약 참고).
- **Next Step:** Phase 3 보완(Gasket·드롭다운) 또는 Phase 4.
- **Blockers:** 없음.

## 2026-04-04: Cursor 프로젝트 규칙 추가

- **작업:** `.cursor/rules/docs-workflow.mdc` 생성 (`alwaysApply: true`).
- **내용 요약:** (1) 작업 시작 전 `docs/` 및 `plan.md` / `progress.md` / `research.md` 맥락 파악. (2) 의미 있는 변경 후 위 세 문서와 구현 상태 동기화.
- **참고:** 이번 항목은 도구·워크플로만 해당하므로 `plan.md`, `research.md` 본문은 변경 없음.

## 2026-04-04: Phase 2 기반 구현 (ClassSpec · Thickness · 제약 로그)

- **목적:** Layer 2 로드맵에 맞춰 클래스 기술 봉투·스케줄 엔진·1차 제약 검증을 코드로 반영.
- **추가/변경 모듈:**
  - `src/excel_sheet_utils.py` — 시트 헤더/셀 읽기 공통화.
  - `src/thickness_engine.py` — Schedule 룩업, `explode_size_range` + `nps_master.nps_list` 사용.
  - `src/class_spec.py` — `ClassSpec` (`TypedDict`), `Class_Define` 로드, Rating/재질 힌트 및 `log_class_constraint_warnings`.
  - `src/pms_generator.py` — 위 모듈 사용으로 리팩터, 생성 시 클래스 대비 경고 로그.
- **스모크:** 빈 템플릿 생성 → PMS 출력까지 실행 확인.
- **비고:** 보간·엄격 재질 화이트리스트 등은 사용자 규칙 입력 시 확장.

## 2026-04-04: 재질 매핑 DB · Rating(B16.5 vs B16.11) 구분

- **data/class_material_mapping.json:** `base_material_allowlist` — `Class_Base_Material`(대문자 키)별 허용 ASTM/규격 부분 문자열. `config.class_material_mapping_path()`.
- **class_spec:** KCS 등 매핑에 있으면 allowlist로만 재질 힌트; B16.5 Class(150…)와 B16.11(3000…)은 서로 비교하지 않음(ASME B16.5 vs B16.11).

## 2026-04-04: RCS/RES 이음 표기

- **규칙:** `L`/`S` = Large/Small 단면(NPS), `B` = Both(양끝 동일 → BBE·PBE·TBE). `Size1`/`End_Type_1`·`Size2`/`End_Type_2` 짝으로 대소 판별 후 토큰 조합.
- **코드:** `pms_generator._rcs_res_end_type_token`, Reducing_Table 전개 시 `reducer_size1`/`reducer_size2` 전달.

## 2026-04-04: 템플릿 생성 출력 경로

- **변경:** GUI「템플릿 생성」시 선택 폴더 아래 `template/YYYYMMDD_HHMMSS/` 에 `Class_Define_Template.xlsx` 저장. GUI「자재 클래스 생성」시 선택 폴더 아래 `output/YYYYMMDD_HHMMSS/` 에 `Piping_Material_Class_Data.xlsx` 저장 (`controller`).

---
*Last Updated: 2026-04-05 (Branch_Table 22×10 정리, gitignore·동기화)*
