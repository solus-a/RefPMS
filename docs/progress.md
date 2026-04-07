# Project Progress Report

이 문서는 구현 이력을 시간순으로 관리합니다.  
로드맵은 `docs/plan.md`, 설계 해설은 `docs/research.md`를 기준으로 합니다.

---

## 현재 상태 (2026-04-07)

- **Current Phase:** Phase 3 완료
- **최근 완료:** `Gasket_Group` 반영 + 테스트 하네스 도입
- **다음 우선순위:** 하네스 실케이스 축적, Phase 4(원자 속성 구조화) 착수
- **Blockers:** 없음

---

## 2026-04-07

### 1) Gasket_Group 반영

- `pms_generator` 처리 대상에 `Gasket_Group` 추가
- 가스켓 전용 설명 조합 로직 반영  
  (`Gasket_Type`, 재질 조합, `IR/OR`, `Rating/Facing/Thickness/Dim_Standard`)
- `Thickness1`은 `Schedule`이 아니라 입력 `Thickness`를 그대로 사용(입력/출력 1:1)
- `component_mapping` / `data_defaults`에 타입별 `conditional_required` 구체화
- `template_generator`에 `Gasket_Group` 시트 기본 생성 + `Item_Code_DB` 기본행 `G` 추가

### 2) 테스트 하네스 도입

- `tests/harness_core.py`  
  - 케이스 탐지 (`tests/input` ↔ `tests/expected` 미러 구조)
  - 생성 실행 + 엑셀 시트/행 diff 비교
- `tests/harness_runner.py`  
  - `--all`, `--case`, `--input/--expected` 실행 경로
  - 종료코드 규약: 성공 `0`, 실패 `1`, 사용 오류 `2`
- `tests/test_harness.py`  
  - 자동 탐지 케이스 일괄 검증 (케이스 없으면 skip)
- `run.py`  
  - `python run.py harness ...` 커맨드 추가 (GUI 경로와 분리)

---

## 2026-04-06

- Flange 시트명을 `Flange` → `Flange_Group`으로 통일
- Flange 헤더 `End_Type` → `Flange_Type` 정리
- Flange 설명 규칙 보강 (SW/WN만 SCH 표기)
- Branch_Table에서 `TH` 처리 보강 (`Size2` 기준 1회 전개)
- Thread 표기 규칙 정리 (`project_info.thread_method`, 현재 `NPT`)
- 출력 열 9개(`Class_Name`~`Item_Name`)로 고정, `Remarks` 출력 열 제거
- `PL`(PLUG) 설명 토큰 예외 반영

---

## 2026-04-05

- Item_Code DB 스키마 정리 (`Catalog_Item_Name`, `Description_Prefix`)
- `ensure_all_program_data_files()`로 JSON/DB 선행 보장
- Pipe 니플(JN/JNP/JNT 계열) 길이/설명/발주명 규칙 정비
- 엘보 LR/SR 표기 규칙 정비 (B16.9 vs B16.11)
- Reducing/Swage 설명 및 `Dim_Standard` 정규화 규칙 반영
- Branch_Table(`T`,`RT`) 전개/정렬 규칙 반영
- `.gitignore`에 로컬 산출물(`build-output/`, `.vscode/`) 정책 반영

---

## 2026-04-04

- Phase 1~2 기반 모듈 구현 (`config`, `class_spec`, `thickness_engine`, `pms_generator`)
- 재질 allowlist 및 B16.5/B16.11 등급 분리 검증 적용
- RCS/RES 이음 토큰 규칙 반영
- 템플릿/출력 경로 타임스탬프 구조 적용 (`template/`, `output/`)
- 문서 워크플로 룰 추가 (`docs-workflow`, `folder-naming`)

---

*Last Updated: 2026-04-07*
