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

| # (✅ 해결) | 심각도 | 내용 | 원인 |
|---|---|---|---|
| F1 ✅ | 치명 | Forged·Wrought Fitting 전 행 `Item_Description` 빈 값 | 생성기가 레거시 `data/Item_Code_DB.xlsx`를 읽음. 그 파일의 Group이 분리 전 이름(`Fitting_Group`, `Valve_Group`)이라 시트명과 불일치 → 빈 문자열 반환 |
| F2 ✅ | 치명 | 같은 코드(E 등)의 Forged↔Wrought 이름 뒤바뀜 (0.5" 단조 엘보가 `ELBOW 90 DEG LR`) | 레거시 xlsx가 Item_Code 하나로만 키잉 (그룹 구분 없음) |
| F3 ✅ | 치명 | GUI(json)에 있는 11개 코드가 xlsx에 없음: FR, FB, F8, FBS, JB, JFR, JP, JU, VN, SE, TR → FB가 `FLANGE … WN`으로 잘못 나오고 VN Item_Name 빈 값 | Item Code 소스가 json(GUI)·xlsx(생성기) 두 개로 갈라짐 |
| F4 ✅ | 치명 | Global Size Selection에서 끈 크기(1.25, 2.5, 3.5, 5, 22)가 산출물에 전개됨 — 상위 제약 위반 | 생성기가 `size_selection`/`active_sizes_for_class`를 전혀 참조하지 않음 |
| F5 | 큼 | Description이 GUI 미리보기와 다름: 밸브(Operation 토큰 누락, 다른 토큰 추가), 볼트(`STUD BOLT BOLT A307-B / HEX NUTS NUT A194-2H`) | 생성기에 GUI `_DESCRIPTION_SPECS`와 별개인 description 로직 |
| F6 | 큼 | `Commodity_Code` 224/224 빈 값 | 미구현 |
| F7 ✅ | 중 | Forged Fitting rating을 `CL2000 → 2000#`로 역변환하는 코드 잔존 (CL 통일 결정과 모순; F1 때문에 지금은 드러나지 않음) | 폐지 누락 |
| F8 ✅ | 중 | `Bolt_Length_Table`: 필수인데 값 목록 없음 → 자유입력. 생성기는 비었는지만 확인하고 값은 안 씀. `schema_audit`는 외부 소스로 분류해 문제를 가림 | 값 소스 미정의 |
| F9 | 작음 | GUI가 PIPE(P)에도 Length 입력을 허용 → 미리보기 `PIPE … 50mm`, 산출물은 무시 | 조건부 빈 값 규칙 없음 |
| F10 ✅ | 중 | Blind Flange(FB)·Spectacle 등에도 `Flange_Type`(WN/SO/LJ/SW/THRD)이 필수 → `BLIND FLANGE A105 WN …`, 생성기는 WN이면 Schedule까지 붙임 | 필수 규칙이 Item_Code를 구분하지 않음 |
| ~~F11~~ | — | **오판 정정:** Gate·Globe·Check에는 CL800이 이미 있었음 (1번 실측 때 Needle 선택지만 보고 일반화). 사용자 결정(API 602 범위 Gate·Globe·Check만)과 현 데이터가 일치 → 변경 없음, 테스트로 고정 | — |
| F12 ✅ | 중 | GUI가 Forged Fitting에 SW + CL2000 조합을 허용 — ASME B16.11 §2.1상 SW는 Class 3000/6000/9000, 2000은 나사식 전용 | End_Type↔Rating 규칙 없음 |
| F13 ✅ | 작음 | Blind Flange(FB) 행의 `Thickness1`에 배관 Schedule(SCH80/STD)이 들어감 — Blind는 맞물릴 배관 보어가 없어 의미가 불분명 | Flange 두께 = Schedule 일괄 적용 |

정상 확인: Pipe·Flange·Gasket·Valve는 이름과 두께(Schedule 연동)가 기대대로 나옴. Pipe·Flange에 Schedule 토큰이 붙는 것은 의도된 차이 (미리보기는 Class 연동 토큰 제외).

도메인 확인 → 결정: Forged Fitting의 `Thickness1`은 ASME 기준 Rating 표기 (3-3에서 반영).

---

## 2. 안전망 — pytest ✅

실행: `python -m pytest` (설치: `pip install -r requirements-dev.txt`). 현재 **99 passed, 2 xfailed** (F5·F6).

xfail 대응: F5·F6 → `test_generator_e2e.py` (F1·F2/F3·F4·F7·F8·F10·F12는 3번에서 해결되어 일반 테스트로 전환). F9는 아직 테스트 없음 — 고칠 때 추가.

- [x] 2-1. pytest 골격: `pytest.ini`(testpaths, pythonpath=src, xfail_strict), `tests/conftest.py`, `tests/sample_data.py`(리터럴 샘플 — Class A1 + 13그룹)
- [x] 2-2. `tests/test_generator_e2e.py`: 템플릿 왕복·Item Code 누락 없음은 통과. F1·F2/F3·F4·F5·F6·F7은 `xfail(strict)` — 고치면 XPASS로 실패하므로 그때 마커 제거
- [x] 2-3. `tests/test_description_preview.py`: 13그룹 20케이스 골든 + 빈 토큰/구분자 규칙 + Remarks
- [x] 2-4. `tests/test_validation.py`: 필수·조건부 필수(JN Length, FR Size2, SPIRAL WOUND)·크기·Class_Define·Schedule·테이블 참조
  - 조건부 빈 값(`conditional_empty`)은 검증 함수가 없고 GUI 위젯 잠금으로만 처리됨 → 3번/4번 작업 시 검증 함수로 옮길지 결정
- [x] 2-5. `tests/test_schema_consistency.py`: Class_Define 헤더·필수 = 카탈로그, `schema_audit` 이슈 0

## 3. 생성기 SSOT 정렬 (1번 실측으로 신설 — 산출물 정확성)

- [x] 3-1. Item Code: 생성기가 `domain_schema.item_code_entries(sheet)`(json)를 그룹별로 조회 → F1·F2·F3 해소. 레거시 `Item_Code_DB.xlsx`·생성 코드·경로 설정 **전면 폐기**
  - Item_Name = json code_name. Wrought 엘보는 LR/SR 유지 (ASME B16.9: LR Table 6.1-1 / SR Table 6.1-4 — 치수가 다른 별개 부품, §4.1 각인에 반경 구분 없음 → 품목명이 구분을 담아야 함). JN만 code_name + Length
- [x] 3-2. 크기 전개: 이미 계산돼 있던 `class_size_ranges`(Class 범위 ∩ Global Size Selection)로 필터 → F4 해소
- [x] 3-3. Forged Fitting `#` 역변환 제거 → F7 해소. 단조 피팅 `Thickness1` = Rating (ASME B16.11 §2.1), Plug·Bushing은 빈 값 (B16.11 Table 주석), Swage(RCS/RES)는 Schedule 유지 (MSS SP-95)
  - KS·JIS 단조 피팅: field_values Rating에 `SCH80`(std=JIS/KS)이 이미 있어 Thickness1 = Rating 규칙으로 `SCH80`이 그대로 찍힘. 단, GUI 드롭다운에 `SCH80`이 두 번 보임(표시값이 같음) → std 구분 표시 필요
  - Reducing Coupling(JFR)·Bushing(JB) 직접 행은 일반 단조 경로 (Swage만 Schedule 쌍) — 회귀 테스트 `test_forged_reducing_items_do_not_repeat_rating`
  - 4번 때 확인: Swage(RCS/RES, MSS SP-95) Description에 Rating 토큰(CL3000)이 붙는 기존 동작이 맞는지
- [x] 3-4. `Bolt_Length_Table` → 선택 입력, 값 목록 `ASME B16.5` (B16.5 §6.10.2 Table 7·10·13·15·17·19·21 차용). audit 외부 소스 예외 제거 → F8
  - 근거(사용자 결정): 볼트 길이는 개별 자재 특정 정보라 Commodity 단위 PMS에 불필요. 길이 표 데이터는 추후
- [x] 3-5. `Flange_Type`: F·FR일 때만 필수, FB·F8·FBS는 빈 값 (스키마 conditional 규칙 + GUI 잠금) → F10
- [x] 3-6. CL800: Gate·Globe·Check에 이미 존재 — 변경 없음, `test_cl800_only_on_api602_valve_groups`로 고정 (F11 오판 정정)
- [x] 3-7. Forged End_Type↔Rating Constraint (ASME B16.11 §2.1): 규칙 데이터 `domain_schema.FORGED_RATING_BY_END_TYPE`, GUI 드롭다운 필터 + 저장 차단, 생성기 validator에서도 행 제외. JIS·KS Sch80 제외 → F12
  - 규칙 변경에 따른 기존 데이터: 프로젝트·템플릿을 불러올 때 conditional_empty 필드를 비움 (`component_row_clear_conditional_empty`) → GUI에서 내보낸 템플릿은 항상 현행 규칙. 목록에 없는 옛 저장값은 선택 입력 필드에서만 편집 창에 보존 (필수 필드는 빈칸으로 보여 다시 고르게 함)
  - 주의: 엑셀을 직접 고쳐 CLI 생성기에 넣은 규칙 위반 행은 로그 경고만 남기고 산출물에서 빠짐 → **7번(GUI 생성)에서 제외된 행을 사용자에게 보여 줄 것**
  - 주의(UX): 편집 창을 열 때 규칙에 맞지 않는 기존 값(SW+CL2000의 Rating, FB의 Flange_Type)은 안내 없이 비워짐 — 저장 시 필수 경고로는 드러남
- [x] 3-8. Flange `Thickness1`은 WN·SW만 Schedule, 나머지(SO·LJ·THRD·FB·F8·FBS)는 빈 값 → F13. Description의 SCH 토큰과 같은 상수(`FLANGE_BORE_MATCHED_TYPES`) 사용
  - 근거: WN은 용접 끝 보어를 배관 두께에 맞춤(B16.5 §7.7), SO·LJ는 배관 외경에 끼우는 형식(§7.7.1 보어 공차), Blind는 보어 없음
- [ ] 3-10. closed set 소속 검사: GUI 저장·엔진 모두 필드값이 field_values 목록에 있는지 검사하지 않음 (옛 값 보존 때문에 목록 밖 값이 다시 저장될 수 있음). 검사 도입 여부 결정
- [ ] 3-11. (도메인 확인) Reducing Flange(FR)+WN의 Schedule 기준 크기: 지금은 Thickness1·Description SCH가 큰 쪽(Size1) 기준. WN 허브·보어는 작은 쪽 배관에 맞추므로 Size2 기준이 맞는지 확인 필요
- [x] 3-9. 문서 정합: Flange·Gasket·Valve 9개 Rating 정의의 "Matl_Std 로 거름" 문구를 실제 동작(전체 목록 표시)으로 정정. Pipe Matl_Code 설명의 낡은 내용(category 키 없음·없는 함수명·엔진 검증 없음)도 정정
- 후보(미확정): B16.9 3D 엘보(Table 6.1-6) Item Code 추가 / SR 엘보(ES·ES4) 사용 시 경고 규칙 (SR은 Jacket Elbow 외 사용 제한 — 사용자 도메인 지식)

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

## 7.5 UI 지침 (7번 완료 후 착수 — 사용자 결정 2026-09-24)

기준: awesome-design-md 의 IBM DESIGN.md. ttk 테마는 vista 유지.

- [ ] 7.5-1. `docs/DESIGN.md` 작성 — Stitch 9섹션 형식 중 데스크톱 tkinter 에 해당하는 것만 (색 역할·간격·규칙·Do/Don't) + 표(Treeview/Listbox) 규칙 추가
  - IBM 값: canvas `#ffffff`, surface `#f4f4f4`, hairline `#e0e0e0`, ink `#161616`, muted `#525252`, primary `#0f62fe`, success `#24a148`, warning `#f1c21b`, error `#da1e28`, 간격 4/8/12/16/24/32, 모서리 0·그림자 없음
  - 글꼴은 맑은 고딕 유지 (IBM Plex 미설치·한글 미지원). 웹 전용 섹션(반응형·히어로·푸터) 제외
- [ ] 7.5-2. `src/ui_theme.py` 토큰 모듈 — 코드에 흩어진 16진수 색(약 30종) 교체
- [ ] 7.5-3. vista 테마에서 무시되는 스타일 확인 (예: 콤보박스 경고 배경 `Warn.TCombobox`) — 화면 확인 필요

## 8. Commodity Code (별도 트랙)

- [ ] 8-1. `Piping Commodity Numbering System(250827_NPJT용).xlsx` 분석 → 자릿수별 규칙 정리
- [ ] 8-2. 규칙을 데이터(SSOT)로 정의 — 필드값 → 코드 매핑
- [ ] 8-3. 생성기 구현, `Commodity_Code` 채움 → F6
- [ ] 8-4. `예시.xlsx`(1740행)와 대조 검증

## 9. 문서 갱신

- [ ] 9-1. ARCHITECTURE.md: 삭제된 모듈 참조 제거, 실제 흐름 반영
- [ ] 9-2. README.md: 실행 명령·경로 검증
