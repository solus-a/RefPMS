# RefPMS v1.0 작업 체크리스트

## 목표

**GUI에서 입력한 프로젝트가 한 흐름으로 최종 PMS(Micro DB: `Piping_Material_Class_Data.xlsx`)까지 — Description과 Commodity Code를 포함해 — 믿을 수 있게 나온다.**

완료 판정 (v1.0 Definition of Done):
- [ ] GUI에서 버튼 하나로 최종 PMS가 생성된다.
- [ ] 산출물이 상위 제약(Global Size Selection, Class 정의)을 지킨다.
- [ ] 같은 부품은 GUI 미리보기와 최종 PMS에서 같은 Description을 가진다.
- [ ] 모든 행에 Commodity Code가 채워진다 (회사 Numbering System 기준).
- [ ] `pytest` 전부 통과, `tools/schema_audit.py` 이슈 0.
- [ ] ARCHITECTURE.md / README.md가 실제 코드와 일치한다.

표기: `[ ]` 미착수 · `[~]` 진행 중 · `[x]` 완료 · `[!]` 막힘(사유 기재)

---

## 1. 현황 실측 — GUI Export → 생성기 흐름이 실제로 도는가 ✅

- [x] 1-1. Export 경로: `_on_export_xlsx` → `_flush_and_validate` → `generate_class_define_template(out, bundle)` → `<폴더>/template/<시각>/Class_Define_Template.xlsx`. 생성기는 같은 로더(`load_class_level_bundle_from_template`)로 읽음.
- [x] 1-2. 샘플: 기존 Export 7개는 Component 행 0개라 사용 불가 → 현재 스키마로 Class 1개 + 13그룹 샘플 번들을 코드로 구성, GUI와 같은 검증 함수 통과.
- [x] 1-3. Export → `pms_generator` 실행: **예외 없이 끝까지 돌고 산출물 224행 생성.**
- [x] 1-4. 판정 → 아래 "발견 사항"
- [x] 1-5. 체크리스트 반영, 우선순위 재조정

### 발견 사항 (2026-09-23 실측)

| # | 심각도 | 내용 | 원인 |
|---|---|---|---|
| F1 | 치명 | Forged·Wrought Fitting 전 행 `Item_Description` 빈 값 | 생성기가 레거시 `data/Item_Code_DB.xlsx`를 읽음. 그 파일의 Group이 분리 전 이름(`Fitting_Group`, `Valve_Group`)이라 시트명과 불일치 → 빈 문자열 반환 |
| F2 | 치명 | 같은 코드(E 등)의 Forged↔Wrought 이름 뒤바뀜 (0.5" 단조 엘보가 `ELBOW 90 DEG LR`) | 레거시 xlsx가 Item_Code 하나로만 키잉 (그룹 구분 없음) |
| F3 | 치명 | GUI(json)에 있는 11개 코드가 xlsx에 없음: FR, FB, F8, FBS, JB, JFR, JP, JU, VN, SE, TR → FB가 `FLANGE … WN`으로 잘못 나오고 VN Item_Name 빈 값 | Item Code 소스가 json(GUI)·xlsx(생성기) 두 개로 갈라짐 |
| F4 | 치명 | Global Size Selection에서 끈 크기(1.25, 2.5, 3.5, 5, 22)가 산출물에 전개됨 — 상위 제약 위반 | 생성기가 `size_selection`/`active_sizes_for_class`를 전혀 참조하지 않음 |
| F5 | 큼 | Description이 GUI 미리보기와 다름: 밸브(Operation 토큰 누락, 다른 토큰 추가), 볼트(`STUD BOLT BOLT A307-B / HEX NUTS NUT A194-2H`) | 생성기에 GUI `_DESCRIPTION_SPECS`와 별개인 description 로직 |
| F6 | 큼 | `Commodity_Code` 224/224 빈 값 | 미구현 |
| F7 | 중 | Forged Fitting rating을 `CL2000 → 2000#`로 역변환하는 코드 잔존 (CL 통일 결정과 모순; F1 때문에 지금은 드러나지 않음) | 폐지 누락 |
| F8 | 중 | `Bolt_Length_Table`: 필수인데 값 목록 없음 → 자유입력. 생성기는 비었는지만 확인하고 값은 안 씀. `schema_audit`는 외부 소스로 분류해 문제를 가림 | 값 소스 미정의 |
| F9 | 작음 | GUI가 PIPE(P)에도 Length 입력을 허용 → 미리보기 `PIPE … 50mm`, 산출물은 무시 | 조건부 빈 값 규칙 없음 |
| F10 | 중 | Blind Flange(FB)·Spectacle 등에도 `Flange_Type`(WN/SO/LJ/SW/THRD)이 필수 → `BLIND FLANGE A105 WN …`, 생성기는 WN이면 Schedule까지 붙임 | 필수 규칙이 Item_Code를 구분하지 않음 |
| F11 | 중 | 밸브 Rating 선택지에 CL800이 없음 — 소구경 단조 밸브의 실무 표준 등급을 고를 수 없음 | field_values 값 누락 |

정상 확인: Pipe·Flange·Gasket·Valve는 이름과 두께(Schedule 연동)가 기대대로 나옴. Pipe·Flange에 Schedule 토큰이 붙는 것은 의도된 차이 (미리보기는 Class 연동 토큰 제외).

도메인 확인 필요: Forged Fitting의 `Thickness1`에 Schedule(SCH80)이 들어감 — 단조 SW 피팅을 Schedule로 표기하는 게 맞는지.

---

## 2. 안전망 — pytest ✅

실행: `python -m pytest` (설치: `pip install -r requirements-dev.txt`). 현재 **47 passed, 7 xfailed**.

xfail 대응: F1·F2/F3·F4·F5·F6·F7 → `test_generator_e2e.py`, F10 → `test_validation.py`. F8·F9·F11은 테스트로 표시하지 않음(샘플이 해당 경로를 타지 않음) — 고칠 때 테스트 추가.

- [x] 2-1. pytest 골격: `pytest.ini`(testpaths, pythonpath=src, xfail_strict), `tests/conftest.py`, `tests/sample_data.py`(리터럴 샘플 — Class A1 + 13그룹)
- [x] 2-2. `tests/test_generator_e2e.py`: 템플릿 왕복·Item Code 누락 없음은 통과. F1·F2/F3·F4·F5·F6·F7은 `xfail(strict)` — 고치면 XPASS로 실패하므로 그때 마커 제거
- [x] 2-3. `tests/test_description_preview.py`: 13그룹 20케이스 골든 + 빈 토큰/구분자 규칙 + Remarks
- [x] 2-4. `tests/test_validation.py`: 필수·조건부 필수(JN Length, FR Size2, SPIRAL WOUND)·크기·Class_Define·Schedule·테이블 참조
  - 조건부 빈 값(`conditional_empty`)은 검증 함수가 없고 GUI 위젯 잠금으로만 처리됨 → 3번/4번 작업 시 검증 함수로 옮길지 결정
- [x] 2-5. `tests/test_schema_consistency.py`: Class_Define 헤더·필수 = 카탈로그, `schema_audit` 이슈 0

## 3. 생성기 SSOT 정렬 (1번 실측으로 신설 — 산출물 정확성)

- [ ] 3-1. Item Code: 생성기가 `domain_schema.item_code_entries(sheet)`(json)를 쓰도록 전환, 그룹별 키잉 → F1·F2·F3 해소. `Item_Code_DB.xlsx` 폐기 여부 결정
- [ ] 3-2. 크기 전개: `active_sizes_for_class` (Class 범위 ∩ Global Size Selection) 적용 → F4 해소
- [ ] 3-3. Forged Fitting `#` 역변환 제거 → F7 해소
- [ ] 3-4. `Bolt_Length_Table` 값 소스 정의 또는 필수 해제 결정, audit 가림 제거 → F8
- [ ] 3-5. Blind/Spectacle/Spacer의 `Flange_Type` 필수 해제 → F10
- [ ] 3-6. 밸브 Rating에 CL800 추가 여부 결정 → F11

## 4. Description 단일화

- [ ] 4-1. 생성기가 GUI의 `_DESCRIPTION_SPECS`를 쓰도록 통합 (Schedule 등 Class 연동 토큰은 확장 슬롯으로) → F5 해소
  - description 조립은 도메인 로직이므로 GUI 모듈(`class_template_wizard`)에서 엔진 모듈로 이동. 테스트 import 경로도 함께 갱신
- [ ] 4-2. 13그룹 전부 미리보기 = 산출물 (2-3 테스트로 고정)
- [ ] 4-3. PIPE(P) Length 조건부 빈 값 규칙 → F9

## 5. Class 값 정리 · SSOT 통일

- [ ] 5-1. Design_Code → `ASME B31.3`만 남김, `field_values.Class_Define`로 이전
- [ ] 5-2. Nominal_Size_System → `field_values.Class_Define`로 이전
- [ ] 5-3. Class_Base_Material 재편 (CS, LAS, SS304, SS304L, SS316/316L Dual Cert., NICKEL, FRP, PVC, CPVC, HDPE; `KCS` → `CS`)
  - 미결: 분류 수준, 허용 규격 목록 위치, 저장 키 표기 → 착수 시 확정
  - 허용 규격 목록 초안 작성 → 사용자 검토
- [ ] 5-4. config / class_spec 하드코드 제거, `schema_audit`에 검사 추가

## 6. Project 레벨 카탈로그

- [ ] 6-1. `PROJECT_FIELDS` 4개 (unit_system, design_temperature_unit, design_pressure_unit, size_selection)
- [ ] 6-2. 기존 코드가 카탈로그에서 파생되도록 연결 + audit 검사

## 7. GUI에서 PMS 생성

- [ ] 7-1. 마법사에 "PMS 생성" 동작 연결 (검증 → 생성 → 결과 경로 안내)
- [ ] 7-2. 생성 실패 시 사용자에게 원인 표시

## 8. Commodity Code (별도 트랙)

- [ ] 8-1. `Piping Commodity Numbering System(250827_NPJT용).xlsx` 분석 → 자릿수별 규칙 정리
- [ ] 8-2. 규칙을 데이터(SSOT)로 정의 — 필드값 → 코드 매핑
- [ ] 8-3. 생성기 구현, `Commodity_Code` 채움 → F6
- [ ] 8-4. `예시.xlsx`(1740행)와 대조 검증

## 9. 문서 갱신

- [ ] 9-1. ARCHITECTURE.md: 삭제된 모듈 참조 제거, 실제 흐름 반영
- [ ] 9-2. README.md: 실행 명령·경로 검증
