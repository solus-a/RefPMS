# Project Progress Report

## 세션 마감 요약 (2026-04-04)

- **코드:** `excel_sheet_utils`, `thickness_engine`, `class_spec`, `pms_generator` 리팩터·동작 정합; `controller` 출력 경로 `template/`·`output/` + `YYYYMMDDHHMMSS`.
- **데이터:** `data/class_material_mapping.json`(재질 allowlist), `project_config.json` NPS/출력 설정.
- **검증:** 정답 `Piping_Material_Class_Data.xlsx`(164행)와 템플릿 생성 결과 일치 확인; 템플릿 단독 생성 스모크 통과.
- **규칙:** `.cursor/rules/docs-workflow.mdc`, `folder-naming.mdc`.
- **다음:** Phase 3(`component_mapping.json`, Validator) 또는 Phase 4/5 로드맵.

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
- **Next Step:** Phase 3(`component_mapping.json`, 동적 Validator).
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

## 2026-04-04: 정답 출력 기준 일치 (RCS/RES 이음 표기)

- **분석:** `output/20260404231609/Piping_Material_Class_Data.xlsx`(164행)와 `template/20260404231357/Class_Define_Template.xlsx` 생성 결과를 대조.
- **차이:** RCS·RES에서 `End_Type_1` BE + `End_Type_2` PE일 때, 양쪽 스케줄 토큰이 같으면 설명에 `PBE`, 다르면 `BLE/PSE` (기존 `BE/PE`·`BE/PE`와 불일치).
- **코드:** `pms_generator._build_item_description_by_rule` 리듀서 분기에 위 규칙 반영.

## 2026-04-04: 템플릿 생성 출력 경로

- **변경:** GUI「템플릿 생성」시 선택 폴더 아래 `template/YYYYMMDDHHMMSS/` 에 `Class_Define_Template.xlsx` 저장. GUI「자재 클래스 생성」시 선택 폴더 아래 `output/YYYYMMDDHHMMSS/` 에 `Piping_Material_Class_Data.xlsx` 저장 (`controller`).

---
*Last Updated: 2026-04-04 (세션 마감 문서 동기화)*
