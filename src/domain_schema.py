"""RefPMS 도메인 데이터 스키마 — Single Source of Truth (SSOT).

각 시트(또는 데이터 그룹)의 필드 정의를 한 곳에 모아 코드 전반의 정합을
보장한다. 다른 모듈은 이 스키마만 참조해 헤더 이름, 필수 여부, 검증 규칙 등을
얻는다.

메타스키마(필드를 정의할 때 살펴볼 9개 측면):
    1. 의미 (meaning)              — 도메인에서 이 필드가 표현하는 것
    2. 데이터 타입 (data_type)     — 문자열 / 숫자 / enum 등
    3. 필수 여부 (required)        — 비어 있으면 에러인지
    4. 형식 제약 (format_constraint) — 정규식·allowlist·길이 제한 등
    5. 중복 (unique)               — 한 프로젝트 내 unique 강제 여부
    6. 다른 필드와의 관계 (relations) — FK / 종속 / 정합 검사
    7. 검증 위치 (validation_location) — 코드의 어느 함수가 검사
    8. 사용자 입력 방법 (input_method) — text entry / combo / auto-filled 등
    9. 단위 (unit)                 — 숫자 필드의 단위 (있을 때만)

특정 항목이 그 필드에 의미 없으면 ``None`` 또는 빈 컬렉션으로 둔다 (N/A).

필드 등록 순서는 해당 시트의 컬럼 순서와 일치시킨다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

import config


@dataclass(frozen=True)
class FieldDefinition:
    """한 필드의 정의 — 메타스키마 9개 항목."""

    name: str
    meaning: str
    data_type: str
    required: bool
    format_constraint: Optional[str] = None
    unique: Optional[bool] = None
    relations: list[str] = field(default_factory=list)
    validation_location: Optional[str] = None
    input_method: Optional[str] = None
    unit: Optional[str] = None
    # 구조화된 교차필드 제약 — data_defaults.DEFAULT_COMPONENT_MAPPING 이 도출.
    # prose 설명은 relations/format_constraint 에도 함께 기술한다.
    conditional_required_when: Optional[dict] = None  # {"field": <sibling>, "values": [...]}
    conditional_empty_when: Optional[dict] = None      # {"field": <sibling>, "values": [...]}


# ── Pipe_Group ─────────────────────────────────────────────────────────────────

PIPE_GROUP_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="Class_Name",
        meaning=(
            "이 행이 속하는 Class의 이름. Class_Define 시트에서 정의된 Class를"
            " 참조하는 외래 키(FK) 역할."
        ),
        data_type="string",
        required=True,
        format_constraint=None,
        unique=None,  # 한 시트 안에 같은 Class_Name 여러 행이 정상
        relations=["Class_Define.Class_Name (FK)"],
        validation_location=None,  # 별도 검증 없음 (wizard 흐름이 보장)
        input_method="auto-filled (wizard에서 Class 선택 시 자동 채움)",
        unit=None,
    ),
    FieldDefinition(
        name="Item_Code",
        meaning=(
            "Item Group(자재 그룹) 안의 Component 분류 short code. 자재 종류"
            "(Pipe / Nipple / Reducer 등)를 식별. RefPMS 내부 data/item_code_db.json"
            "에 등록된 코드만 사용."
        ),
        data_type="string (short alphanumeric code)",
        required=True,
        format_constraint=(
            "data/item_code_db.json 에 등록된 코드 (closed set). 임의 신규 코드 금지."
        ),
        unique=None,  # 같은 Item_Code가 사이즈·재질이 다른 여러 행에 등장 가능
        relations=[
            "item_code_db.json: Item_Code -> Item_Name / Description_Prefix / Group",
            "시트와 item_code_db.Group 이 정합되어야 함"
            " (Pipe_Group 시트는 Group=Pipe_Group 인 코드만 허용)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog의 콤보박스가 시트별 옵션 필터링;"
            " PMS 엔진은 'Item_Code not in DB' 경고."
            " 시트-Group 정합 강제 검증은 추후 별도 작업."
        ),
        input_method=(
            "wizard 컴포넌트 dialog의 콤보박스 (readonly — DB의 코드만 선택 가능)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size_From",
        meaning=(
            "이 component 행이 적용되는 사이즈 범위의 시작값(inclusive)."
            " 단일 사이즈는 Size_From = Size_To 로 표현."
        ),
        data_type="string (catalog NPS or DN value)",
        required=True,
        format_constraint=(
            "data/nps_catalog.json 의 카탈로그 값 (closed set)."
            " Class Size Range = Class_Define.Size_From..Size_To"
            " ∩ Project Size_Selection 안에 있어야 함."
            " Class.Nominal_Size_System(NPS or DN)과 매칭."
        ),
        unique=None,
        relations=[
            "Size_To 와 짝 (Size_From <= Size_To 강제)",
            "Class_Define.Size_From / Size_To (Class Size Range)",
            "Project.Size_Selection 의 활성 사이즈 부분집합",
        ],
        validation_location=(
            "validator.validate_size_range_for_row_dict (Class Size Range 정합);"
            " class_level_model.component_row_size_pair_errors (From <= To)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog의 콤보박스 (readonly — Class별 활성 사이즈만)"
        ),
        unit=(
            "Project.Nominal_Size_System 에 종속:"
            " NPS=무차원 호칭(실제 inch 호칭치, OD와 다름) /"
            " DN=무차원 호칭(실제 mm 호칭치)"
        ),
    ),
    FieldDefinition(
        name="Size_To",
        meaning=(
            "이 component 행이 적용되는 사이즈 범위의 끝값(inclusive)."
            " 단일 사이즈는 Size_From = Size_To 로 표현."
        ),
        data_type="string (catalog NPS or DN value)",
        required=True,
        format_constraint=(
            "data/nps_catalog.json 의 카탈로그 값 (closed set)."
            " Class Size Range 안에 있어야 함."
            " Class.Nominal_Size_System(NPS or DN)과 매칭."
        ),
        unique=None,
        relations=[
            "Size_From 과 짝 (Size_From <= Size_To 강제)",
            "Class_Define.Size_From / Size_To (Class Size Range)",
            "Project.Size_Selection 의 활성 사이즈 부분집합",
        ],
        validation_location=(
            "validator.validate_size_range_for_row_dict (Class Size Range 정합);"
            " class_level_model.component_row_size_pair_errors (From <= To)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog의 콤보박스 (readonly — Class별 활성 사이즈만)"
        ),
        unit=(
            "Project.Nominal_Size_System 에 종속:"
            " NPS=무차원 호칭(실제 inch 호칭치, OD와 다름) /"
            " DN=무차원 호칭(실제 mm 호칭치)"
        ),
    ),
    FieldDefinition(
        name="Matl_Category",
        meaning=(
            "재질의 큰 분류. (CS, LTCS, AS(Cr-Mo), SS, DSS, SDSS, Ni-Alloy,"
            " Cu-Alloy, GI, CI 등 10가지). Matl_Std + Matl_Code 종속 체인의"
            " 최상위 — (Matl_Category, Matl_Std) 페어가 Matl_Code 의 closed"
            " set 을 결정한다."
        ),
        data_type="string (short code, e.g. CS / SS / DSS)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Pipe_Group.Matl_Category 옵션"
            " (closed set, 10개)."
        ),
        unique=None,
        relations=[
            "Matl_Std + Matl_Code 와 종속 체인 형성:"
            " (Matl_Category, Matl_Std) -> Matl_Code 의 closed set",
            "현재 DB(Matl_Code)에 category 필드가 없어 종속 강제 보류 —"
            " Matl_Code 항목에 category 추가 후 wizard 필터 보강 예정",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog의 콤보박스 (closed set 옵션)."
            " 종속 강제 검증은 DB 보강 후 별도 작업."
        ),
        input_method=(
            "wizard 컴포넌트 dialog의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Std",
        meaning=(
            "재질 표준 발행 기관 (ASTM / ASME / JIS / KS / EN / DIN / API)."
            " 구체 표준 코드(예: A106)는 Matl_Code 의 short / long 에 담기고,"
            " 이 필드는 그 코드가 속한 표준 체계를 식별한다."
            " ASME 는 ASTM 의 압력부품 채택판(SA-접두) 표시용으로 별도 등록."
        ),
        data_type="string (short code, e.g. ASTM / ASME / JIS)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Pipe_Group.Matl_Std 옵션"
            " (closed set, 7개: ASTM, ASME, JIS, KS, EN, DIN, API)."
        ),
        unique=None,
        relations=[
            "Matl_Code 와 종속:"
            " Matl_Code 항목의 'std' 키가 이 값과 일치해야 함"
            " (wizard 콤보박스가 std 로 Matl_Code 옵션을 필터링)",
            "Matl_Category 와 함께 (Matl_Category, Matl_Std) -> Matl_Code"
            " 종속 체인의 중간 계층",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set 옵션);"
            " Matl_Code 콤보박스는 선택된 Matl_Std 로 필터링."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Code",
        meaning=(
            "구체 재료 표준 코드/그레이드 (예: A106-B, STPG370). PMS 최종"
            " description 의 핵심 식별자 — _build_pipe_description 에서"
            " <PREFIX> <Matl_Code> <Manufacturing_Method> <End_Type> ..."
            " 토큰으로 합쳐진다. Matl_Std (발행 기관) 안에서 특정 코드/그레이드를"
            " 가리키는 leaf 값."
        ),
        data_type="string (alphanumeric + hyphens, e.g. A106-B)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Pipe_Group.Matl_Code 옵션 (closed set)."
            " 명명 규칙은 std 별 관례를 따른다 (강제 정규식 없음):"
            " ASTM 은 '<코드>-<그레이드>' (A106-B) 또는"
            " '<코드>-<그레이드>-<수정자>' (A672-C60-CL13);"
            " JIS 는 코드 단독 (STPG370, SUS304TP) — 제조방법 접미사는 넣지 않고"
            " Manufacturing_Method 필드에 분리;"
            " EN 은 W.Nr 숫자 표기 (예: 1.0345) 권장."
            " ASME / KS / EN / DIN / API 의 항목 등록은 별도 작업으로 보류."
        ),
        unique=None,
        relations=[
            "Matl_Std -> Matl_Code 종속:"
            " 각 항목의 'std' 키가 Matl_Std 값과 일치 (wizard 콤보박스 필터)",
            "Matl_Category -> Matl_Code 종속은 보류:"
            " DB 항목에 'category' 키가 아직 없음 — 추가 후 wizard 필터 보강 예정",
            "PMS 출력: _build_pipe_description 의 description 토큰",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스"
            " (선택된 Matl_Std 로 std 필터 적용 — _std_filtered_options_for)."
            " PMS 엔진은 description 출력에만 사용 (값 검증 없음)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Manufacturing_Method",
        meaning=(
            "파이프 제조 방법 — Seamless (이음매 없음) 또는 4가지 용접 방식"
            " (ERW / EFW / LSAW / SSAW). PMS description 토큰의 3번째 자리"
            " (예: 'PIPE A106-B SMLS BE'). 사이즈/압력에 따른 관행적 적합 범위는"
            " 존재하나 강제 종속은 두지 않고 사용자 판단에 맡긴다."
        ),
        data_type="string (short code, e.g. SMLS / ERW)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Pipe_Group.Manufacturing_Method"
            " 옵션 (closed set, 5개: SMLS, ERW, EFW, LSAW, SSAW)."
            " 필요 시 DSAW / HFW 추가 가능 — 지금은 보류."
        ),
        unique=None,
        relations=[
            "직접적 FK / 종속 없음 (자유 선택)",
            "사이즈와의 관행적 호환 (예: LSAW≥16\", SSAW≥24\")"
            " 은 도메인 관행 — 강제 안 함",
            "PMS 출력: _build_pipe_description 의 description 토큰",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set 옵션 강제)."
            " PMS 엔진은 description 출력에 사용하며"
            " ['Manufacturing_Method', 'Method'] fallback 으로 옛 헤더도 받음"
            " (legacy — 추후 정리 대상)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="End_Type",
        meaning=(
            "Pipe 행이 표현하는 파이프의 양 끝 가공 형태. 단일 토큰으로 양쪽"
            " 모두를 의미하거나 (PE/BE/TE, PBE/BBE/TBE), 양쪽이 다르면 슬래시로"
            " 두 토큰 결합 (PE/TE(NPT), PE/TE(PT), BE/PE) — 보통 Nipple 등."
            " PMS description 4번째 토큰 (예: 'PIPE A106-B SMLS BE')."
            " SSOT 13 시트 모두 End_Type 단일 컬럼만 사용; reducer/swage 의 양 끝"
            " 차이는 Reducing_Table 에서 별도 표현."
        ),
        data_type="string (short code, e.g. PE / BE / PE/TE(NPT))",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Pipe_Group.End_Type 옵션 (closed set, 9개)."
            " 동의어 주의: PE ≡ PBE, BE ≡ BBE, TE ≡ TBE (ASTM 표준은 PE/BE/TE 만"
            " 사용하며 'Both Ends' 가 default 의미). 회사 관행에 따라 명시적 PBE 표기"
            " 도 유지 — DB 일관성을 위해 한 프로젝트 안에서는 한 표기로 통일 권장."
            " NPT (ASME B1.20.1, US) 와 PT (JIS B0203, JP) 는 별개 나사 표준이므로"
            " 둘 다 유지."
        ),
        unique=None,
        relations=[
            "직접적 FK 없음 (자유 선택)",
            "Item_Code 와의 관행적 호환: Pipe (P) 는 PE/BE 중심,"
            " Nipple (JN) 은 PE/TE(NPT)·PE/TE(PT) 혼합형 — 강제 안 함",
            "PMS description 출력 전용. dimensional standard (ASME B16.9 / B16.11"
            " 등) 결정은 시트별 Dim_Standard 컬럼 / Class_Define 의 design code"
            " 에서 처리.",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set 옵션 강제)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Length",
        meaning=(
            "Nipple component 의 실제 길이 (mm). Item_Code 가 Nipple (JN) 일 때만"
            " 의미를 가지며, Pipe 등 long-pipe 행에서는 빈 값으로 둔다."
            " PMS description / catalog item name 에 반영"
            " (예: 'NIPPLE A106-B SMLS PE/TE(NPT) 100mm')."
        ),
        data_type="string (숫자+단위, e.g. 50mm)",
        required=False,  # 조건부 — Nipple 일 때만 의미. 빈 값 정식 허용.
        format_constraint=(
            "data/field_values.json 의 Pipe_Group.Length 옵션 (closed set, 5개:"
            " 빈 값 / 50mm / 75mm / 100mm / 150mm)."
            " 빈 값은 Pipe 행을 위해 의도적으로 포함."
            " 필요 시 Close Nipple (30mm/40mm) 또는 장형 (200mm+) 추가 가능 — 지금은 보류."
        ),
        unique=None,
        relations=[
            "Item_Code 와 조건부 호환: Nipple (JN) 행에서는 빈 값이 아닌 값이"
            " 필요. Pipe (P 등) 행에서는 빈 값."
            " 강제 검증은 두지 않고 wizard 콤보박스가 빈 값 옵션 제공 — 사용자 판단.",
            "PMS 출력: _try_nipple_pipe_output 의 description 토큰 및"
            " _apply_length_to_catalog_nipple_name 의 catalog name 변형.",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + 빈 값)."
            " PMS 엔진은 Nipple item code 분기에서만 사용."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만, 빈 값 포함)"
        ),
        unit=(
            "mm (실제 길이 — Pipe Size 시스템 NPS/DN 과 무관하게 mm 일관)"
        ),
        conditional_required_when={"field": "Item_Code", "values": ["JN"]},
    ),
    FieldDefinition(
        name="Option_Code",
        meaning=(
            "Item_Code 변종/옵션 식별자 — 같은 Class · 같은 Pipe_Group 안에서"
            " component 행을 유일하게 식별하는 보조 키. 형식은 3자리 숫자 텍스트"
            " (예: '001', '051', '105')."
            " '001' = 해당 Class 의 design concept 에 부합하는 표준형 (non-variant)."
            " 예시: 'small size 는 socket welding' 인 Class 에서 small size range"
            " 의 PE/BE pipe 는 default 가 아니므로 변종 (001 이 아닌 다른 코드)."
            " 변종 코드의 의미 매핑은 Option_Code 옵션 풀이 채워지면서 확립."
        ),
        data_type="string (3자리 0-9 숫자 텍스트, 앞자리 0 보존; e.g. '001')",
        required=True,
        format_constraint=(
            "정규식 ^\\d{3}$ — 정확히 3자리 숫자. 텍스트로 저장 (앞자리 0 보존)."
            " data/field_values.json 의 Pipe_Group.Option_Code 옵션 (closed set)."
            " 현재 '001' (default) 한 개만 등록 — 변종 코드는 도메인 합의에 따라"
            " 점진적으로 추가."
        ),
        unique=(
            "(Class_Name, Option_Code) 가 Pipe_Group 시트 안에서 유일."
            " Group 경계 unique 가 아님 — 같은 Class 의 Forged_Fitting_Group.001"
            " 과 Pipe_Group.001 은 공존 정상 (시트별로 독립적 default 가짐)."
            " 강제 검증은 별도 작업 (현재 미구현)."
        ),
        relations=[
            "(Class_Name, Option_Code) 가 Pipe_Group 행의 자연 키 (natural key)",
            "'001' 의 도메인적 의미 = 해당 Class · Pipe_Group 의 표준형 ↔"
            " Class_Define 의 design concept (예: 'small size 는 SW') 에 따라"
            " 결정. 변종 (001 외) 은 그 concept 에서 벗어나는 행 — 예: 같은 size"
            " range 인데 다른 end_type / matl_code / manufacturing 조합",
            "Item_Code 와 직교적: 같은 Item_Code 안에서 여러 Option_Code 가 존재"
            " 가능 (default + 변종들)",
            "PMS 엔진 (pms_generator.py) 은 현재 Option_Code 미참조 — 향후 행"
            " 식별/정렬/description 합성 통합 여지 (별도 작업)",
        ],
        validation_location=(
            "형식 검증 (^\\d{3}$): wizard 컴포넌트 dialog 입력 시점 (현재 미구현)."
            " Required 검증: data_defaults.DEFAULT_COMPONENT_MAPPING 의"
            " Pipe_Group.required_non_empty 에 'Option_Code' 포함 (등록 완료)."
            " (Class_Name, Option_Code) unique 검증: bundle/class 레벨에서 별도"
            " 작업 필요 (현재 미구현)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)."
            " 옵션 풀이 작은 동안은 콤보 + 자유 입력 혼합 검토 가능 — 단,"
            " 3자리 숫자 형식 강제."
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Remarks",
        meaning=(
            "행 단위 비고/설명 자유 텍스트 — 표준 필드로 표현하기 어려운 보조"
            " 정보를 기록 (예: 특수 가공 요구, 프로젝트 특이사항, 임시 참고 메모)."
            " Pipe_Group 에서는 PMS description 의 마지막 토큰으로 그대로 합성되어"
            " 출력에 노출됨 (Item_Description 끝부분)."
        ),
        data_type="string (자유 텍스트, 빈 값 허용)",
        required=False,
        format_constraint=(
            "형식 강제 없음 — data/field_values.json 의 _meta.free_input_fields"
            " 에 'Remarks' 명시. closed set 미적용."
            " 단, 길이 정보는 Length 컬럼 전용 — Remarks 에 길이를 적어도 PMS"
            " 엔진은 폴백 사용하지 않음 (옛 설계 잔재 정리됨, pms_generator"
            " _try_nipple_pipe_output 주석 참조)."
        ),
        unique=None,
        relations=[
            "PMS description 합성의 마지막 토큰 —"
            " class_template_wizard._build_pipe_description,"
            " pms_generator._try_pipe_output / _try_nipple_pipe_output 등에서"
            " Item_Description 끝에 공백 join 으로 추가",
            "출력 Remarks 컬럼에 그대로 보존 (pms_generator 의 out_remarks)",
            "Length 와 의미적으로 분리 — 길이는 Length 컬럼, 자유 메모는 Remarks."
            " 같은 텍스트가 두 곳에 중복 노출되지 않도록 사용자 판단",
        ],
        validation_location=(
            "검증 없음 (자유 입력)."
            " required 아님 —"
            " data_defaults.DEFAULT_COMPONENT_MAPPING 의 Pipe_Group"
            " required_non_empty 미포함."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 자유 텍스트 입력 (Entry widget)."
            " 단일 줄 권장 — Excel 셀 표시 가독성."
        ),
        unit=None,
    ),
]


# ── Wrought_Fitting_Group ──────────────────────────────────────────────────────
#
# Wrought fitting (압연/단조 이후 추가 가공으로 만든 fitting) — ASME B16.9 / JIS /
# KS / EN 의 butt-welded fitting 영역. Item_Code 라인업: 90° / 45° elbow (LR/SR),
# tee, reducing tee, concentric / eccentric reducer, swage, cap, stub end (12종).
#
# Pipe_Group 과 비교한 시트 특성:
#   - Length 컬럼 없음 (wrought fitting 은 길이가 아닌 standard dim 기반)
#   - End_Type 옵션 풀이 BW 단일 (현재 시점 — Grooved End / mechanical joint 는 미고려)
#   - Manufacturing_Method 옵션 풀이 SMLS / WLD 2개 (Pipe 의 ERW/EFW/LSAW/SSAW 무관)
#   - Matl_Category 7개 (CS/LTCS/AS/SS/DSS/SDSS/Ni-Alloy)
#       · Cu-Alloy / CI 는 wrought 가능하나 현재 미구현 (추후 도메인 합의 시 추가)
#       · GI 는 coating 영역 — wrought 의 재질 카테고리 주제와 다름 (분리 처리)
#   - Matl_Std 4개 (ASME/DIN/API 제외 — fitting 표준의 핵심은 ASTM/JIS/KS/EN)
#   - Matl_Code 10개 모두 ASTM (다른 std 항목은 추후 도메인 합의에 따라 등록)

WROUGHT_FITTING_GROUP_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="Class_Name",
        meaning=(
            "이 행이 소속될 Class 의 이름 — Class_Define 시트의 Class_Name 행에"
            " 존재해야 함. Pipe_Group.Class_Name 과 의미·검증 모두 동일 (3계층"
            " hierarchy 의 Class 키)."
        ),
        data_type="string",
        required=True,
        format_constraint=(
            "공백 trim. 일치 검사는 Class_Define.Class_Name 행 집합 기준."
        ),
        unique=None,
        relations=[
            "Class_Define.Class_Name 으로 FK — 미존재 Class 참조 불가",
        ],
        validation_location=(
            "Pipe_Group.Class_Name 과 동일 패턴 — 현재 wizard 컴포넌트 dialog 의"
            " 콤보박스가 Class_Define 행 목록을 closed set 으로 제공."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class_Define 행 목록)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Item_Code",
        meaning=(
            "Wrought_Fitting_Group 의 component 종류 식별자."
            " 12종: E/ES (90° LR/SR elbow), E4/ES4 (45° LR/SR elbow), T (tee),"
            " TR (reducing tee), RC (concentric reducer), RE (eccentric reducer),"
            " RCS/RES (swage concentric/eccentric), CP (cap), SE (stub end)."
            " PMS description 의 prefix 토큰으로 사용 (item_code_db 의 code_name)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/item_code_db.json 의 Wrought_Fitting_Group 행 (closed set, 12개)."
            " 외부 DB 참조 — field_values.json 에는 없음."
        ),
        unique=None,
        relations=[
            "item_code_db.json Wrought_Fitting_Group 의 code 값 중 하나 (FK)",
            "PMS description prefix 합성: code → code_name (예: E → ELBOW 90 DEG LR)",
            "Reducer 계열 (RC/RE/RCS/RES) 과 reducing tee (TR) 는 size pair 의미가"
            " 다름 — Reducing_Table / Branch_Table 의 size 쌍과 정합 (별도 검증 영역)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set 옵션 강제)."
            " PMS 엔진에서는 item_code_db.code 일치 검사."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — item_code_db 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size_From",
        meaning=(
            "이 행이 다루는 NPS/DN size 범위의 하한. Pipe_Group.Size_From 과"
            " 의미·형식 동일."
        ),
        data_type="string (NPS or DN token, e.g. '1/2', '2', '12')",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 에 맞춰 NPS / DN catalog 의 한"
            " 항목. Pipe_Group.Size_From 과 동일 검증."
        ),
        unique=None,
        relations=[
            "Class_Define.Size_From / Size_To 범위 안 (Class 가 허용한 size 범위)",
            "(Size_From, Size_To) 는 component 행의 size 적용 범위 — Size_From <= Size_To",
            "Reducer / reducing tee (RC/RE/RCS/RES/TR) 의 경우 Size_From 은 main size",
        ],
        validation_location=(
            "Pipe_Group.Size_From 과 동일 패턴 —"
            " class_level_model.component_row_size_pair_errors 가 Size_From <= Size_To"
            " 를 강제 (현재 Pipe_Group 만; Wrought 도 같은 규칙 적용 예정)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위"
            " 안 NPS/DN catalog)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size_To",
        meaning=(
            "이 행이 다루는 NPS/DN size 범위의 상한. Pipe_Group.Size_To 와"
            " 의미·형식 동일."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS / DN catalog."
            " Size_From <= Size_To 강제 (행 단위 검증)."
        ),
        unique=None,
        relations=[
            "(Size_From, Size_To) 의 상한",
            "Reducer 의 경우 Size_To 는 reducing 후 branch/outlet size 가 아닌"
            " main size 의 상한 — branch size 는 다른 컬럼 (시트별 정책)",
        ],
        validation_location=(
            "Pipe_Group.Size_To 와 동일 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Category",
        meaning=(
            "재질의 대분류 카테고리. Pipe_Group.Matl_Category 와 의미 동일."
            " 옵션 풀은 7개 (CS, LTCS, AS, SS, DSS, SDSS, Ni-Alloy)."
            " 미포함 항목 처리 정책:"
            "\n - Cu-Alloy / CI (Cast Iron): 도메인적으로 wrought fitting 재질이"
            "   될 수 있으나 현재 시스템에서는 미구현 — 도메인 합의 시 추가 가능."
            "\n - GI (Galvanized Iron): 갈바나이즈드는 coating 의 일환이므로"
            "   wrought fitting 의 재질 카테고리 주제와 다름 (추후에도 추가 안 함;"
            "   필요 시 별도 coating 필드/시트로 분리 검토)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Wrought_Fitting_Group.Matl_Category 옵션"
            " (closed set, 7개: CS, LTCS, AS, SS, DSS, SDSS, Ni-Alloy)."
        ),
        unique=None,
        relations=[
            "Matl_Std / Matl_Code 와 종속 체인 — Matl_Code DB 의 std 키와 카테고리"
            " 가 일치하는 항목만 허용 (Pipe_Group 패턴과 동일)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
            " Matl_Code 필터링의 1차 게이트."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Std",
        meaning=(
            "재질 표준 발행 기관. Pipe_Group.Matl_Std 와 의미 동일."
            " Wrought fitting 영역의 표준 — ASTM (A234/A403/A420 등), JIS, KS, EN."
            " ASME (보일러·압력용기 표준), DIN (EN 으로 통합), API (oil&gas"
            " 특수 fitting; ASTM 베이스 인용) 는 일반 wrought fitting 시트에서 제외."
        ),
        data_type="string (short code, e.g. ASTM / JIS)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Wrought_Fitting_Group.Matl_Std 옵션"
            " (closed set, 4개: ASTM, JIS, KS, EN)."
        ),
        unique=None,
        relations=[
            "Matl_Code 의 std 키와 일치 (Matl_Code DB 필터링의 2차 게이트)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Code",
        meaning=(
            "Wrought fitting 의 구체 재질 규격 코드. Pipe_Group.Matl_Code 와 의미"
            " 동일 — 표준 + 등급 (예: ASTM A234 WPB, A403 WP304)."
            " 'WP' 접두는 wrought fitting 규격 특유의 grade marker (A234-WPB 등)."
        ),
        data_type="string (short code, e.g. A234-WPB)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Wrought_Fitting_Group.Matl_Code 옵션"
            " (closed set, 10개 — 모두 ASTM). JIS/KS/EN 항목은 도메인 합의에"
            " 따라 추후 추가 (Pipe_Group 과 같은 보류 정책)."
            " 명명 규칙은 자유형 + std 별 관례 (Pipe_Group.Matl_Code 와 동일)."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK), Matl_Category (의미적 정합) 와 함께 표시 — 콤보박스"
            " 가 std/category 별 필터링",
            "Matl_Code DB 의 'std' 키로 Matl_Std 와 강제 정합 (Pipe_Group 패턴 동일)",
            "PMS description 에 그대로 합성 (예: 'ELBOW A234-WPB SMLS BW')",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Manufacturing_Method",
        meaning=(
            "Wrought fitting 의 제조 공정. Pipe_Group.Manufacturing_Method 와"
            " 같은 컬럼명이지만 옵션 풀은 wrought fitting 특화: SMLS (Seamless —"
            " 압연·인발로 이음새 없이 성형) / WLD (Welded — 판재를 굽혀 용접 조립)."
            " Pipe 의 ERW/EFW/LSAW/SSAW 같은 long-pipe 전용 공정은 무관."
        ),
        data_type="string (short code, SMLS / WLD)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Wrought_Fitting_Group.Manufacturing_Method"
            " 옵션 (closed set, 2개: SMLS, WLD)."
        ),
        unique=None,
        relations=[
            "Matl_Code 와의 호환 관행: A234-WPB 등 SMLS/WLD 둘 다 가능;"
            " WP304/316 도 둘 다 — 강제 검증 없음, 사용자 판단",
            "PMS description 에 합성 (예: 'ELBOW A234-WPB SMLS BW')",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="End_Type",
        meaning=(
            "Wrought fitting 의 단부 형식. 현재 옵션 풀은 BW 단일 (ASME B16.9"
            " 등 표준 wrought fitting 의 기본 단부)."
            " Socket weld / threaded 단부는 forged fitting (Forged_Fitting_Group)"
            " 영역이므로 wrought 시트에 등장하지 않음."
            " 넓게 보면 Grooved End (Mechanical Joint) 같은 비-welded 단부도"
            " wrought fitting 에 적용 가능하지만 현재 시스템에서는 고려하지 않음"
            " (추후 도메인 합의 시 옵션 풀 확장 검토)."
        ),
        data_type="string (short code, BW)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Wrought_Fitting_Group.End_Type 옵션"
            " (closed set, 1개: BW). 현재 시점의 시트 정의는 사실상 wrought = BW."
        ),
        unique=None,
        relations=[
            "Pipe_Group.End_Type (PE/BE/TE 등) 과 의미적으로 독립 — wrought 는"
            " butt-weld 단부 전제",
            "PMS 엔진의 Reducer / Tee 처리에서 End_Type 으로 dimensional standard"
            " (ASME B16.9 등) 결정",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만, 사실상 BW 고정)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Option_Code",
        meaning=(
            "Item_Code 변종/옵션 식별자. Pipe_Group.Option_Code 와 의미·형식 동일"
            " — 3자리 숫자 텍스트, '001' = 해당 Class · Wrought_Fitting_Group 의"
            " 표준형 (non-variant)."
        ),
        data_type="string (3자리 0-9 숫자 텍스트; e.g. '001')",
        required=True,
        format_constraint=(
            "정규식 ^\\d{3}$. data/field_values.json 의 Wrought_Fitting_Group."
            "Option_Code 옵션 (closed set). 현재 '001' 한 개만 등록."
        ),
        unique=(
            "(Class_Name, Option_Code) 가 Wrought_Fitting_Group 시트 안에서 유일."
            " Pipe_Group / 다른 시트의 Option_Code 와는 독립 (시트별 독립 default)."
        ),
        relations=[
            "(Class_Name, Option_Code) 가 Wrought_Fitting_Group 행의 자연 키",
            "'001' 의 도메인적 의미 = 해당 Class · Wrought_Fitting_Group 의 표준형."
            " 예: 'small size SW' Class 라도 wrought fitting 시트의 default 는"
            " 여전히 BW 표준형 — 시트별 default 가 독립적임을 보여주는 예시",
            "Pipe_Group.Option_Code 와 동일 패턴 (자세한 검증·미구현 사항은"
            " Pipe_Group.Option_Code 정의 참조)",
        ],
        validation_location=(
            "Pipe_Group.Option_Code 와 동일 패턴 — 형식 / required / unique 검증"
            " 모두 현재 미구현 (별도 작업)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Remarks",
        meaning=(
            "행 단위 비고/설명 자유 텍스트. Pipe_Group.Remarks 와 의미·동작 동일"
            " — PMS description 의 마지막 토큰으로 합성."
        ),
        data_type="string (자유 텍스트, 빈 값 허용)",
        required=False,
        format_constraint=(
            "형식 강제 없음 — data/field_values.json 의 _meta.free_input_fields"
            " 에 'Remarks' 명시 (모든 시트 공통)."
        ),
        unique=None,
        relations=[
            "PMS description 합성의 마지막 토큰 — Pipe_Group.Remarks 와 동일 패턴",
        ],
        validation_location=(
            "검증 없음 (자유 입력). required 아님."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 자유 텍스트 입력 (Entry widget)"
        ),
        unit=None,
    ),
]


# ── Forged_Fitting_Group ───────────────────────────────────────────────────────
#
# Forged fitting (단조 후 가공으로 만든 small-bore fitting) — ASME B16.11 /
# JIS B 2316 / KS 의 socket weld & threaded fitting 영역. Small size 에서는
# butt weld 가 잘 쓰이지 않으므로 SW / threaded 단부의 elbow / tee / coupling /
# bushing / plug / union 등을 사용. Reducing 이 필요할 때는 swage 또는
# reducing coupling 으로 처리.
#
# Wrought_Fitting_Group 과의 핵심 차이:
#   - Manufacturing_Method 컬럼 없음 (forging 이 단일 공정 — 별도 필드 불요)
#   - Rating 컬럼 신설 (std-aware: ASTM 은 Class designation 2000-9000#;
#     JIS/KS 는 Sch80 schedule 표기)
#   - End_Type = SW / PT / NPT 3개 (small-bore 의 socket weld / threaded)
#   - Item_Code 12종: E/E4 (90°/45° elbow), T (tee), RCS/RES (concentric/
#     eccentric swage — reducing 수단), CP (cap), JF (full coupling),
#     JFR (reducing full coupling), TH (half coupling), JU (union), JP (plug),
#     JB (bushing). Wrought 에 있던 RC/RE 같은 butt-weld reducer 는 forged
#     영역에 없음 (small-bore 에서는 swage / reducing coupling 으로 대체).
#   - Matl_Code 11개 (ASTM A105 / A350-LF2 / A182-F 계열 8 + JIS SF440A /
#     SUS304-F / SUS316-F 3). 'F' 접미가 JIS forged grade marker.
#   - Matl_Category 7개 / Matl_Std 4개 — Wrought 와 동일 정책 (Cu-Alloy/CI
#     보류, GI 는 coating 별도 주제).
#
# BSP (R/Rc) 같은 영국 표준 thread 단부는 현재 미고려 (추후 합의 시 확장).

FORGED_FITTING_GROUP_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="Class_Name",
        meaning=(
            "이 행이 소속될 Class 의 이름. Pipe_Group.Class_Name 과 의미·검증"
            " 모두 동일."
        ),
        data_type="string",
        required=True,
        format_constraint=(
            "공백 trim. Class_Define.Class_Name 행 집합 기준 일치 검사."
        ),
        unique=None,
        relations=[
            "Class_Define.Class_Name 으로 FK",
        ],
        validation_location=(
            "Pipe_Group.Class_Name 과 동일 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class_Define 행 목록)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Item_Code",
        meaning=(
            "Forged_Fitting_Group 의 component 종류 식별자."
            " 12종: E (90° elbow), E4 (45° elbow), T (tee),"
            " RCS / RES (concentric / eccentric swage — small-bore 의 reducing 수단),"
            " CP (cap),"
            " JF (full coupling), JFR (reducing full coupling), TH (half coupling),"
            " JU (union), JP (plug), JB (bushing)."
            " Wrought 의 RC/RE 같은 butt-weld reducer 는 forged 영역에 없음 —"
            " small-bore 에서는 BW 자체를 잘 안 쓰므로 swage / reducing coupling"
            " 으로 대체."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/item_code_db.json 의 Forged_Fitting_Group 행 (closed set, 12개)."
        ),
        unique=None,
        relations=[
            "item_code_db.json Forged_Fitting_Group 의 code 값 중 하나 (FK)",
            "PMS description prefix 합성: code → code_name (예: JFR → REDUCING FULL COUPLING)",
            "Reducing 계열 (RCS/RES/JFR/JB) 은 size pair 의미가 다름 — Size_From /"
            " Size_To 의 의미가 main/branch 분리될 수 있음 (시트별 정책 별도 정의)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set 옵션 강제)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — item_code_db 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size_From",
        meaning=(
            "이 행이 다루는 NPS/DN size 범위의 하한. Pipe_Group.Size_From 과"
            " 의미·형식 동일. Forged fitting 은 small-bore (대체로 NPS 2 이하)"
            " 영역에 집중."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog 의 한 항목."
            " Size_From <= Size_To 강제 (행 단위 검증)."
        ),
        unique=None,
        relations=[
            "Class_Define.Size_From / Size_To 범위 안",
            "(Size_From, Size_To) = component 행의 size 적용 범위 — Size_From <= Size_To",
            "Reducing 항목 (RCS/RES/JFR/JB) 에서는 Size_From 이 main size, 분기/축소된"
            " size 는 별도 필드 없이 swage/coupling 의 도메인 관행으로 처리",
        ],
        validation_location=(
            "Pipe_Group.Size_From 과 동일 패턴 (component_row_size_pair_errors)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size_To",
        meaning=(
            "이 행이 다루는 NPS/DN size 범위의 상한. Pipe_Group.Size_To 와"
            " 의미·형식 동일."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size_From <= Size_To 강제."
        ),
        unique=None,
        relations=[
            "(Size_From, Size_To) 의 상한",
        ],
        validation_location=(
            "Pipe_Group.Size_To 와 동일 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Category",
        meaning=(
            "재질의 대분류 카테고리. Wrought_Fitting_Group.Matl_Category 와"
            " 정책 동일 — 7개 (CS/LTCS/AS/SS/DSS/SDSS/Ni-Alloy)."
            " Cu-Alloy / CI 는 forged fitting 영역에서도 가능하나 현재 미구현."
            " GI 는 coating 영역으로 wrought 와 마찬가지로 재질 카테고리에서 제외."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Forged_Fitting_Group.Matl_Category 옵션"
            " (closed set, 7개)."
        ),
        unique=None,
        relations=[
            "Matl_Std / Matl_Code 와 종속 체인 (Pipe_Group 패턴 동일)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Std",
        meaning=(
            "재질 표준 발행 기관. Wrought_Fitting_Group.Matl_Std 와 옵션 풀 동일"
            " (ASTM / JIS / KS / EN). Forged 영역의 핵심 표준은 ASTM A105 / A182"
            " 와 JIS SF / SUS-F 계열."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Forged_Fitting_Group.Matl_Std 옵션"
            " (closed set, 4개: ASTM, JIS, KS, EN)."
        ),
        unique=None,
        relations=[
            "Matl_Code 의 std 키와 일치 (Matl_Code DB 필터링)",
            "Rating 의 std 키와도 일치 — std-aware Rating 필터링 (이 시트 특유)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Code",
        meaning=(
            "Forged fitting 의 구체 재질 규격 코드. ASTM A105 (CS), A350-LF2"
            " (LTCS), A182-F304/316/304L/316L/F11/F22 (SS/AS forged grade);"
            " JIS SF440A (CS), SUS304-F / SUS316-F (SS). 'F' 접미가 JIS forged"
            " grade marker."
        ),
        data_type="string (short code, e.g. A105 / SF440A)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Forged_Fitting_Group.Matl_Code 옵션"
            " (closed set, 11개: ASTM 8 + JIS 3). KS/EN 항목은 추후 도메인 합의에"
            " 따라 추가."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK), Matl_Category (의미적 정합) 와 함께 표시 — 콤보박스"
            " 가 std/category 별 필터링",
            "PMS description 에 그대로 합성 (예: 'ELBOW A105 SW 3000#')",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Rating",
        meaning=(
            "Forged fitting 의 압력 등급 (pressure class / schedule)."
            " std-aware 필드 — 표준별로 표기 체계가 다름:"
            "\n - ASTM (ASME B16.11): Class 2000# / 3000# / 6000# / 9000#."
            "   2000# 는 threaded only, 9000# 는 socket weld only;"
            "   3000# / 6000# 는 SW · threaded 공통."
            "\n - JIS (JIS B 2316) / KS: Class designation 미사용 — Schedule"
            "   표기 (Sch80) 만 사용. 라벨/표기는 'Sch80' 단일."
            " 다른 시트의 Rating (Flange 의 150#/300#/..., wrought 에는 컬럼 자체"
            " 없음) 과 의미·옵션 풀 모두 독립."
        ),
        data_type="string (short code; ASTM 은 NNNN# 형식, JIS/KS 는 SchNN 형식)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Forged_Fitting_Group.Rating 옵션"
            " (closed set, std 키 포함). ASTM 4 + JIS 1 + KS 1 = 6 entries"
            " — JIS/KS 가 short='Sch80' 으로 중복되므로 dialog 는 std 필터링"
            " 후 매칭되는 long 라벨을 표시."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK) — std-aware 필터링의 1차 게이트",
            "End_Type 과 호환 관행:"
            "   ASTM 2000# ↔ threaded (PT/NPT) only,"
            "   ASTM 9000# ↔ SW only,"
            "   ASTM 3000#/6000# ↔ SW · threaded 공통,"
            "   JIS/KS Sch80 ↔ SW · threaded 공통 (B 2316 / B 2316S)"
            " — 강제 검증은 별도 작업, 현재 wizard 는 자유 조합 허용",
            "PMS description 에 합성 (예: 'ELBOW A105 SW 3000#')",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
            " End_Type 호환 강제 검증은 미구현 (별도 작업)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중 Matl_Std"
            " 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="End_Type",
        meaning=(
            "Forged fitting 의 단부 형식. small-bore 의 socket weld / threaded."
            " SW (Socket Weld) / PT (Threaded, JIS B 0203 — 일본 테이퍼 thread)"
            " / NPT (Threaded, ASME B1.20.1 — US 테이퍼 thread)."
            " BSP (R/Rc, 영국 표준 thread) 는 현재 미고려."
            " Butt weld 단부는 wrought fitting (Wrought_Fitting_Group) 영역."
        ),
        data_type="string (short code, SW / PT / NPT)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Forged_Fitting_Group.End_Type 옵션"
            " (closed set, 3개)."
        ),
        unique=None,
        relations=[
            "Rating 과 호환 관행 (위 Rating.relations 참조 — 강제 검증 없음)",
            "Item_Code 에 따른 End_Type 제약 관행: union (JU) / plug (JP) /"
            " bushing (JB) 은 threaded 일색이 보통, 강제는 아님",
            "PMS description 에 합성 (예: 'ELBOW A105 SW 3000#')",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Option_Code",
        meaning=(
            "Item_Code 변종/옵션 식별자. Pipe_Group.Option_Code 와 의미·형식"
            " 동일 — 3자리 숫자 텍스트, '001' = 해당 Class · Forged_Fitting_Group"
            " 의 표준형 (non-variant)."
        ),
        data_type="string (3자리 0-9 숫자 텍스트; e.g. '001')",
        required=True,
        format_constraint=(
            "정규식 ^\\d{3}$. data/field_values.json 의 Forged_Fitting_Group."
            "Option_Code 옵션 (closed set). 현재 '001' 한 개만 등록."
        ),
        unique=(
            "(Class_Name, Option_Code) 가 Forged_Fitting_Group 시트 안에서 유일."
            " 다른 시트의 Option_Code 와는 독립."
        ),
        relations=[
            "(Class_Name, Option_Code) 가 Forged_Fitting_Group 행의 자연 키",
            "Pipe_Group.Option_Code 와 동일 패턴 (자세한 검증·미구현 사항은"
            " Pipe_Group.Option_Code 정의 참조)",
        ],
        validation_location=(
            "Pipe_Group.Option_Code 와 동일 패턴 — 형식 / required / unique"
            " 검증 모두 현재 미구현."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Remarks",
        meaning=(
            "행 단위 비고/설명 자유 텍스트. Pipe_Group.Remarks 와 의미·동작 동일"
            " — PMS description 의 마지막 토큰으로 합성."
        ),
        data_type="string (자유 텍스트, 빈 값 허용)",
        required=False,
        format_constraint=(
            "형식 강제 없음 — data/field_values.json 의 _meta.free_input_fields"
            " 에 'Remarks' 명시 (모든 시트 공통)."
        ),
        unique=None,
        relations=[
            "PMS description 합성의 마지막 토큰 — Pipe_Group.Remarks 와 동일 패턴",
        ],
        validation_location=(
            "검증 없음 (자유 입력). required 아님."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 자유 텍스트 입력 (Entry widget)"
        ),
        unit=None,
    ),
]


# ── Flange_Group ───────────────────────────────────────────────────────────────
#
# Flange (관과 관 또는 관과 장비를 연결하는 분리 가능한 이음재) — 단조 grade
# 재질 사용 (Forged_Fitting_Group 과 Matl_Code 옵션 풀 완전 동일). 종류는
# 두 축으로 분리:
#   - Item_Code: 일반 flange 와 의미가 크게 다른 line-blank 류를 분리
#     (F / FB / F8 / FBS)
#   - Flange_Type: 일반 flange (F) 안에서의 형식 분류 (WN/SO/LJ/SW/THRD/RD)
#
# 다른 시트와 비교한 특성:
#   - Size 시스템: Size1_From/To + Size2_From/To (Reducing flange 용 두 번째 size)
#     · Size2 는 Item_Code=FR (Reducing flange) 행에서만 의미; 다른 Item_Code 는 빈 값
#   - Rating 옵션 풀 20개 (ASTM 6 + JIS 7 + KS 7), std-aware (Forged Rating 패턴 따름)
#     · ASTM (ASME B16.5): 150 / 300 / 600 / 900 / 1500 / 2500#
#     · JIS (JIS B 2220):  5K / 10K / 16K / 20K / 30K / 40K / 63K
#     · KS  (KS B 1503):   5K / 10K / 16K / 20K / 30K / 40K / 63K
#     · short 값에 "JIS5K", "KS5K" 식 prefix 포함 — std 키 없어도 식별 가능하지만
#       콤보박스 필터링 일관성을 위해 std 키도 부여
#   - End_Type / Manufacturing_Method 컬럼 없음 (Facing + Flange_Type 으로
#     단부 + 형식 표현, manufacturing 은 forging 단일이라 별도 필드 불요)
#   - Item_Code 'BL' 은 Flange_Type 에서 제거 (Item_Code=FB 와 의미 중복 방지)
#
# 미고려 항목 (추후 도메인 합의 시 확장):
#   - Facing: LM/LF (Large Male/Female), SM/SF (Small Male/Female)
#   - Flange_Type: LWN (Long Weld Neck), Orifice flange
#   - Item_Code: Orifice flange (별도 분리 안 함)

FLANGE_GROUP_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="Class_Name",
        meaning=(
            "이 행이 소속될 Class 의 이름. Pipe_Group.Class_Name 과 의미·검증"
            " 모두 동일."
        ),
        data_type="string",
        required=True,
        format_constraint=(
            "공백 trim. Class_Define.Class_Name 행 집합 기준 일치 검사."
        ),
        unique=None,
        relations=[
            "Class_Define.Class_Name 으로 FK",
        ],
        validation_location=(
            "Pipe_Group.Class_Name 과 동일 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class_Define 행 목록)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Item_Code",
        meaning=(
            "Flange_Group 의 component 종류 식별자. 5종:"
            " F (일반 flange — 연결용; 세부 형식은 Flange_Type 컬럼으로 구분),"
            " FR (Reducing flange — 두 size 의 flange 일체화. Item Code 자체가"
            " reducing 특성 'Y' 를 가지며, 그 안의 Flange_Type 은 WN/SO/LJ/SW/"
            "THRD 중 결정 — ASME B16.5 정합),"
            " FB (Blind flange — line-blank, 한 면이 막힘),"
            " F8 (Spectacle Blind — 8자 모양 line-blank, 회전으로 open/close),"
            " FBS (Paddle Spacer & Blank — 막대형 spacer 또는 blank)."
            " 일반 flange / reducing flange / line-blank 의 의미 차이가 커서"
            " Item_Code 로 분리; 일반 flange 안에서의 WN/SO/LJ/SW/THRD 구분은"
            " Flange_Type 으로 처리."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/item_code_db.json 의 Flange_Group 행 (closed set, 5개)."
        ),
        unique=None,
        relations=[
            "item_code_db.json Flange_Group 의 code 값 중 하나 (FK)",
            "Flange_Type 과의 의미 분리: Item_Code ∈ {F, FR} 일 때만 Flange_Type"
            " 이 의미를 가짐 (WN/SO/LJ/SW/THRD). FB/F8/FBS 행에서는 Flange_Type"
            " 이 N/A — 강제 검증은 별도 작업",
            "Item_Code=FR 일 때 Size2_From/Size2_To 필수 (conditional_required);"
            " Item_Code ∈ {F, FB, F8, FBS} 일 때 Size2 비어야 함"
            " (conditional_empty) — component_mapping.json 에서 강제",
            "PMS description prefix 합성: F → FLANGE, FR → REDUCING FLANGE,"
            " FB → BLIND FLANGE, F8 → SPECTACLE BLIND, FBS → PADDLE SPACER & BLANK",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set 옵션 강제)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — item_code_db 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size1_From",
        meaning=(
            "주(main) NPS/DN size 범위의 하한. 다른 시트의 Size_From 과 같은"
            " 의미지만 Flange 는 size 가 두 짝 (main / branch) 가능한 행을"
            " 가지므로 'Size1' / 'Size2' 로 분리 표기."
            " Reducing flange (Item_Code=FR) 에서는 large end size."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size1_From <= Size1_To 강제 (행 단위 검증, 별도 작업으로 구현 예정)."
        ),
        unique=None,
        relations=[
            "Class_Define.Size_From / Size_To 범위 안",
            "(Size1_From, Size1_To) 는 component 행의 주 size 적용 범위",
            "Size2_From / Size2_To 와의 관계: Item_Code=FR 일 때 Size1 = large,"
            " Size2 = small (Reducing direction). 다른 Item_Code 에서는 Size2"
            " 빈 값.",
        ],
        validation_location=(
            "Pipe_Group.Size_From 패턴 — component_row_size_pair_errors 확장 필요"
            " (현재 Pipe_Group 만; Flange 도 Size1/Size2 두 짝 모두 검증 예정)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size1_To",
        meaning=(
            "주(main) NPS/DN size 범위의 상한. Size1_From 의 상한 짝."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size1_From <= Size1_To 강제."
        ),
        unique=None,
        relations=[
            "(Size1_From, Size1_To) 의 상한",
        ],
        validation_location=(
            "Pipe_Group.Size_To 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size2_From",
        meaning=(
            "부(small end) NPS/DN size 범위의 하한 — Reducing flange 전용 필드."
            " Item_Code=FR 행에서만 의미를 가지며, 그 외 Item_Code"
            " (F/FB/F8/FBS) 행에서는 빈 값."
            " Reducing direction 관행: Size1 = large end, Size2 = small end."
        ),
        data_type="string (NPS or DN token; 빈 값 허용 — 조건부)",
        required=False,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size2_From <= Size2_To 강제 (행 단위)."
            " Reducing 관행: Size2 < Size1 (smaller end) — 강제는 별도 작업."
        ),
        unique=None,
        relations=[
            "Item_Code=FR 일 때 필수, 그 외에는 빈 값"
            " (conditional_required / conditional_empty rule)",
            "Size1 / Size2 의 reducing direction (Size1 > Size2) 정합 검사 필요",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 에서 Item_Code 선택에 따라 enable/disable"
            " (별도 작업으로 구현 예정)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)."
            " Item_Code=FR 일 때만 활성화."
        ),
        unit=None,
        conditional_required_when={"field": "Item_Code", "values": ["FR"]},
        conditional_empty_when={"field": "Item_Code", "values": ["F", "FB", "F8", "FBS"]},
    ),
    FieldDefinition(
        name="Size2_To",
        meaning=(
            "부(small end) NPS/DN size 범위의 상한 — Reducing flange 전용."
            " Size2_From 의 상한 짝."
        ),
        data_type="string (NPS or DN token; 빈 값 허용 — 조건부)",
        required=False,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size2_From <= Size2_To 강제."
        ),
        unique=None,
        relations=[
            "(Size2_From, Size2_To) 의 상한",
            "Item_Code=FR 일 때 필수",
        ],
        validation_location=(
            "Size2_From 과 동일 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스. Item_Code=FR 일 때만 활성화."
        ),
        unit=None,
        conditional_required_when={"field": "Item_Code", "values": ["FR"]},
        conditional_empty_when={"field": "Item_Code", "values": ["F", "FB", "F8", "FBS"]},
    ),
    FieldDefinition(
        name="Matl_Category",
        meaning=(
            "재질의 대분류 카테고리. Wrought/Forged_Fitting_Group 과 동일 정책"
            " — 7개 (CS/LTCS/AS/SS/DSS/SDSS/Ni-Alloy)."
            " Cu-Alloy / CI 보류, GI 는 coating 영역으로 제외."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Flange_Group.Matl_Category 옵션"
            " (closed set, 7개)."
        ),
        unique=None,
        relations=[
            "Matl_Std / Matl_Code 와 종속 체인 (Pipe_Group 패턴 동일)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Std",
        meaning=(
            "재질 표준 발행 기관. Wrought/Forged 와 동일 옵션 (ASTM/JIS/KS/EN)."
            " Forged flange 의 핵심 표준은 ASTM A105/A182 와 JIS SF/SUS-F 계열."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Flange_Group.Matl_Std 옵션"
            " (closed set, 4개)."
        ),
        unique=None,
        relations=[
            "Matl_Code 의 std 키와 일치",
            "Rating 의 std 키와도 일치 — std-aware Rating 필터링",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Code",
        meaning=(
            "Flange 의 구체 재질 규격 코드. Forged_Fitting_Group.Matl_Code 와"
            " 옵션 풀 완전 동일 (11개 — ASTM 8 + JIS 3) — 두 시트 모두 forged grade"
            " 를 사용하기 때문. 'F' suffix 가 forged grade marker"
            " (A182-F304, SUS304-F)."
        ),
        data_type="string (short code, e.g. A105 / SF440A)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Flange_Group.Matl_Code 옵션"
            " (closed set, 11개). KS/EN 항목은 추후 추가."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK), Matl_Category (의미적 정합) 와 함께 필터링",
            "Forged_Fitting_Group.Matl_Code 와 옵션 풀 동일 — 동일 forged grade 사용",
            "PMS description 에 그대로 합성 (예: 'FLANGE A105 RF 150# WN')",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Rating",
        meaning=(
            "Flange 의 압력 등급. std-aware 필드 — 표준별 표기 체계가 다름:"
            "\n - ASTM (ASME B16.5): Class 150 / 300 / 600 / 900 / 1500 / 2500#."
            "\n - JIS (JIS B 2220): 5K / 10K / 16K / 20K / 30K / 40K / 63K."
            "\n - KS (KS B 1503): 5K / 10K / 16K / 20K / 30K / 40K / 63K (JIS 호환)."
            " short 값에 'JIS5K' / 'KS5K' 식 prefix 가 이미 포함되어 있어 두 표준의"
            " 5K 가 별개 short 로 식별됨. std 키는 콤보박스 필터링용 보조."
            " Forged_Fitting_Group.Rating (Sch80) 과는 의미·옵션 풀 모두 독립."
        ),
        data_type="string (short code; ASTM 은 NNN# 형식, JIS/KS 는 prefix+NK 형식)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Flange_Group.Rating 옵션 (closed set, 20개)."
            " ASTM 6 + JIS 7 + KS 7. std 키 부여 — Matl_Std 와 필터링 정합."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK) — std-aware 필터링의 1차 게이트",
            "Facing 과 호환 관행: 600#+ 는 RTJ 가 흔함, 150#-300# 는 RF/FF —"
            " 강제 검증 없음, 사용자 판단",
            "PMS description 에 합성 (예: 'FLANGE A105 RF 150# WN')",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중 Matl_Std"
            " 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Facing",
        meaning=(
            "Flange 접촉면(face)의 가공 형식. 6개:"
            " RF (Raised Face — 가장 흔함),"
            " FF (Flat Face — cast iron flange 와의 짝),"
            " RTJ (Ring Type Joint — 고압용),"
            " MF (Male Face), FM (Female Face),"
            " TG (Tongue and Groove — male/female 짝 중 일부 명칭)."
            " LM/LF / SM/SF (Large/Small Male-Female) 는 현재 미고려."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Flange_Group.Facing 옵션 (closed set, 6개)."
        ),
        unique=None,
        relations=[
            "Rating 과 호환 관행 (위 Rating.relations 참조)",
            "Gasket_Group 의 Facing 과 짝 — flange face 와 gasket face 는 일치해야"
            " 정합 (별도 검증 영역)",
            "PMS description 에 합성 (예: 'FLANGE A105 RF 150# WN')",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Flange_Type",
        meaning=(
            "Flange 의 형식 구분 (face/neck/end 결합 방식). 5개:"
            " WN (Weld Neck — 용접 + neck 보강, 가장 흔함),"
            " SO (Slip-On — 파이프 위에 끼우고 용접),"
            " LJ (Lap Joint — stub end 와 함께 사용, 회전 가능),"
            " SW (Socket Weld — small bore 의 socket 접합),"
            " THRD (Threaded — 나사 접합)."
            " BL (Blind) 은 Item_Code=FB, RD (Reducing) 은 Item_Code=FR 로"
            " 분리되었기에 옵션 풀에서 제외 (Item_Code 와 Flange_Type 의 도메인"
            " 직교성 — ASME B16.5 정합: Reducing Flange 도 어떤 Flange_Type"
            " 인지 결정해야 함)."
            " LWN (Long Weld Neck), Orifice flange 등은 현재 미고려."
            " Item_Code=FB/F8/FBS 행에서는 Flange_Type 이 의미 없음 (빈 값)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Flange_Group.Flange_Type 옵션"
            " (closed set, 5개)."
            " Item_Code ∈ {F, FR} 일 때만 의미; FB/F8/FBS 행에서는 N/A"
            " (조건부 검증은 별도 작업)."
        ),
        unique=None,
        relations=[
            "Item_Code 와 직교 — Item_Code ∈ {F, FR} 일 때만 의미",
            "Size2_From/To 와의 조건부 관계는 Item_Code=FR 으로 이관"
            " (Flange_Type 으로는 더 이상 reducing 결정하지 않음)",
            "PMS description 에 합성 (Flange_Type 토큰)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
            " Item_Code 와의 조건부 검증은 별도 작업."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)."
            " Item_Code ∈ {F, FR} 일 때만 활성화."
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Option_Code",
        meaning=(
            "Item_Code 변종/옵션 식별자. Pipe_Group.Option_Code 와 의미·형식"
            " 동일 — 3자리 숫자 텍스트, '001' = 해당 Class · Flange_Group 의 표준형."
        ),
        data_type="string (3자리 0-9 숫자 텍스트; e.g. '001')",
        required=True,
        format_constraint=(
            "정규식 ^\\d{3}$. data/field_values.json 의 Flange_Group.Option_Code"
            " 옵션 (closed set). 현재 '001' 한 개만 등록."
        ),
        unique=(
            "(Class_Name, Option_Code) 가 Flange_Group 시트 안에서 유일."
            " 다른 시트의 Option_Code 와는 독립."
        ),
        relations=[
            "(Class_Name, Option_Code) 가 Flange_Group 행의 자연 키",
            "Pipe_Group.Option_Code 와 동일 패턴",
        ],
        validation_location=(
            "Pipe_Group.Option_Code 와 동일 패턴 — 검증 모두 현재 미구현."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Remarks",
        meaning=(
            "행 단위 비고/설명 자유 텍스트. Pipe_Group.Remarks 와 의미·동작 동일."
        ),
        data_type="string (자유 텍스트, 빈 값 허용)",
        required=False,
        format_constraint=(
            "형식 강제 없음 — data/field_values.json 의 _meta.free_input_fields"
            " 에 'Remarks' 명시 (모든 시트 공통)."
        ),
        unique=None,
        relations=[
            "PMS description 합성의 마지막 토큰 — Pipe_Group.Remarks 와 동일 패턴",
        ],
        validation_location=(
            "검증 없음 (자유 입력). required 아님."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 자유 텍스트 입력 (Entry widget)"
        ),
        unit=None,
    ),
]


# ── Gasket_Group ───────────────────────────────────────────────────────────────
#
# Gasket (두 flange 사이의 밀봉용 부품) — Pipe/Fitting/Flange 와 재질 체계가
# 완전히 다름 (forged grade 가 아니라 시트·필러·링 재질 조합). 따라서:
#   - Matl_Category / Matl_Std / Matl_Code 일반 필드 사용하지 않음 — 대신
#     Gasket 전용 Material_Primary / Material_Secondary 두 필드로 구조 재질 표현
#   - Item_Code 는 'G' 하나만; 종류는 Gasket_Type 컬럼으로 구분 (SHEET/SW/RTJ)
#   - Size 는 단일 짝 (Size_From/Size_To) — Reducing gasket 은 거의 없음
#
# Gasket_Type 별 의미·재질 사용 패턴 (Material_Primary / Material_Secondary):
#   - SHEET (Sheet Gasket, Non-metallic):
#       Primary  = sheet 본체 재질 (Non-Asbestos / PTFE / Graphite)
#       Secondary = 빈 값 (단일 재질)
#   - SW (Spiral Wound, Semi-metallic):
#       Primary  = 'metal+filler' 합쳐진 표기 (SS304+Graphite, SS316+PTFE 등)
#       Secondary = SW 의 outer/inner ring 재질 (CS / SS304 / SS316)
#       · Winding 과 Filler 를 별도 필드로 분리하지 않고 Primary 한 토큰에 합침
#         (도메인 결정 — '+' 로 구분 표기)
#   - RTJ (Ring Type Joint, Metallic):
#       Primary  = ring 재질 (Soft-Iron / SS304 / SS316)
#       Secondary = 빈 값 (단일 재질)
#
# 미고려 항목 (추후 도메인 합의 시 확장):
#   - Gasket_Type: Metal Jacketed (MJ), Kammprofile / Camprofile (CMG)
#   - Sheet 재질: Aramid Fiber, Glass Fiber, Mica, Ceramic
#   - SW Winding 재질: SS321, Inconel-600/625, Monel-400, Hastelloy-C276
#   - Reducing gasket (Size2 컬럼) — 거의 사용 안 함
#   - Facing 옵션: MF/FM/TG/LM/LF/SM/SF — Gasket 은 flange face 짝이므로
#     RF/FF/RTJ 3개로 시작 (Flange Facing 의 부분집합)
#   - Item_Code 분리: GR (RTJ 전용) 등 — 현재 G 하나로 유지, Type 컬럼으로 구분
#   - Thickness: 0.5/0.8/1.0/2.0/5.0mm 등 — 현재 1.5/3.0/4.5/6.0 4개로 시작
#
# 다른 시트와의 차이:
#   - Pipe/Fitting/Flange: forged grade Matl_Code 11종 std-aware
#     vs Gasket: 시트·필러·링 재질 (Matl_Code 미사용, Material_Primary/Secondary)
#   - Flange: Size1/Size2 두 짝 (Reducing 지원)
#     vs Gasket: Size_From/Size_To 한 짝
#   - Flange: Facing 6개
#     vs Gasket: Facing 3개 (Flange face 의 일반 짝만)

GASKET_GROUP_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="Class_Name",
        meaning=(
            "이 행이 소속될 Class 의 이름. Pipe_Group.Class_Name 과 의미·검증"
            " 모두 동일."
        ),
        data_type="string",
        required=True,
        format_constraint=(
            "공백 trim. Class_Define.Class_Name 행 집합 기준 일치 검사."
        ),
        unique=None,
        relations=[
            "Class_Define.Class_Name 으로 FK",
        ],
        validation_location=(
            "Pipe_Group.Class_Name 과 동일 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class_Define 행 목록)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Item_Code",
        meaning=(
            "Gasket_Group 의 component 종류 식별자. 현재 'G' (GASKET) 하나만 정의."
            " Gasket 종류 (SHEET/SW/RTJ) 는 Item_Code 가 아니라 Gasket_Type 컬럼으로"
            " 구분 — Flange_Group 의 line-blank 류 (FB/F8/FBS) 같은 의미 차이가"
            " gasket 류에서는 크지 않기 때문."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/item_code_db.json 의 Gasket_Group 행 (closed set, 현재 1개)."
        ),
        unique=None,
        relations=[
            "item_code_db.json Gasket_Group 의 code 값 중 하나 (FK)",
            "PMS description prefix 합성: G → GASKET",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set 옵션 강제)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — item_code_db 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size_From",
        meaning=(
            "NPS/DN size 범위의 하한. Pipe_Group.Size_From 과 의미 동일."
            " Gasket 은 Reducing 거의 없음 — 단일 size 짝 (Size_From/Size_To) 사용."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size_From <= Size_To 강제 (행 단위 검증, 별도 작업으로 구현 예정)."
        ),
        unique=None,
        relations=[
            "Class_Define.Size_From / Size_To 범위 안",
        ],
        validation_location=(
            "Pipe_Group.Size_From 패턴 — component_row_size_pair_errors 확장 필요."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size_To",
        meaning=(
            "NPS/DN size 범위의 상한. Size_From 의 상한 짝."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size_From <= Size_To 강제."
        ),
        unique=None,
        relations=[
            "(Size_From, Size_To) 의 상한",
        ],
        validation_location=(
            "Pipe_Group.Size_To 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Gasket_Type",
        meaning=(
            "Gasket 의 구조적 분류. 3종:"
            " SHEET (Sheet Gasket — non-metallic 단일 시트),"
            " SW (Spiral Wound — semi-metallic, metal winding + filler + outer/inner ring),"
            " RTJ (Ring Type Joint — metallic, 고압용 solid metal ring)."
            " 이 필드가 Material_Primary / Material_Secondary 의 의미를 결정."
            " Item_Code 가 아니라 별도 컬럼으로 분리한 이유: gasket 의 의미 자체는"
            " 동일 (밀봉)하고 구조만 다르기 때문 — line-blank 류처럼 의미가 완전히"
            " 다른 변종이 아님."
            " Metal Jacketed (MJ), Camprofile (CMG) 등은 현재 미고려."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Gasket_Group.Gasket_Type 옵션"
            " (closed set, 3개)."
        ),
        unique=None,
        relations=[
            "Material_Primary / Material_Secondary 의 의미·옵션 풀 결정",
            "Rating 과 호환 관행: RTJ 는 600#+ 고압용이 흔함",
            "Facing 과 호환 관행: RTJ gasket 은 Facing=RTJ 와 짝",
            "PMS description 에 합성 (gasket type 토큰)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
            " Material_Primary 와의 조건부 검증은 별도 작업."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Material_Primary",
        meaning=(
            "Gasket 의 주(primary) 재질. Gasket_Type 별로 의미가 다름:"
            "\n - SHEET: 시트 본체 재질 (Non-Asbestos / PTFE / Graphite)."
            "\n - SW: Winding 금속 + Filler 비금속의 조합 한 토큰"
            " (SS304+Graphite, SS304+PTFE, SS316+Graphite, SS316+PTFE 4종)."
            "\n - RTJ: solid metal ring 재질 (Soft-Iron / SS304 / SS316)."
            " 통합 풀 (10개) 에서 Gasket_Type 별로 일부만 의미 — 콤보박스 필터링은"
            " 별도 작업 (Gasket_Type 종속). Pipe/Fitting/Flange 의 Matl_Code 와"
            " 완전히 별개의 옵션 풀."
        ),
        data_type="string (short code; SW 일 때 'A+B' 형식)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Gasket_Group.Material_Primary 옵션"
            " (closed set, 10개)."
        ),
        unique=None,
        relations=[
            "Gasket_Type 과 조건부 호환 — Gasket_Type 별로 의미 있는 옵션이 다름"
            " (Sheet 시 'Non-Asbestos'/'PTFE'/'Graphite', SW 시 'SS304+Graphite' 등,"
            " RTJ 시 'Soft-Iron'/'SS304'/'SS316'). 강제 검증은 별도 작업.",
            "Material_Secondary 와 종속: Gasket_Type=SW 일 때만 Secondary 가 의미"
            " (outer/inner ring 재질). Sheet/RTJ 시 Secondary 는 빈 값.",
            "PMS description 에 합성 (gasket material 토큰)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + Gasket_Type 종속)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중"
            " Gasket_Type 과 호환되는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Material_Secondary",
        meaning=(
            "Gasket 의 부(secondary) 재질 — Spiral Wound 의 outer/inner ring 재질"
            " 전용 필드 (4종: 빈 값 / CS / SS304 / SS316)."
            " Gasket_Type 별 사용 패턴:"
            "\n - SW: outer/inner ring 재질 (CS / SS304 / SS316). 두 ring 재질을"
            " 같다고 가정 — 다를 경우는 추후 분리 (현재 미고려)."
            "\n - SHEET / RTJ: 빈 값 (단일 재질이므로 secondary 없음)."
        ),
        data_type="string (short code; 빈 값 허용 — 조건부)",
        required=False,
        format_constraint=(
            "data/field_values.json 의 Gasket_Group.Material_Secondary 옵션"
            " (closed set, 4개 — 빈 값 포함)."
            " Gasket_Type=SW 일 때만 required; Sheet/RTJ 시 빈 값 (조건부 검증은"
            " 별도 작업)."
        ),
        unique=None,
        relations=[
            "Gasket_Type 과 조건부 호환 — SW 일 때만 의미",
            "Material_Primary 와 함께 SW 의 재질 조합 표현",
            "PMS description 에 합성 (SW 일 때 ring 재질 토큰)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
            " Gasket_Type=SW 일 때만 활성화 (별도 작업)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)."
            " Gasket_Type=SW 일 때만 활성화."
        ),
        unit=None,
        conditional_required_when={"field": "Gasket_Type", "values": ["SPIRAL WOUND"]},
    ),
    FieldDefinition(
        name="Rating",
        meaning=(
            "Gasket 의 압력 등급. Flange_Group.Rating 과 옵션 풀 완전 동일 (20개)"
            " — gasket 은 flange 와 짝이므로 같은 rating 체계 사용."
            " std-aware: ASTM 6 (150-2500#) + JIS 7 (5K-63K) + KS 7 (5K-63K)."
            " short 값에 'JIS5K'/'KS5K' 식 prefix 포함 — 두 표준의 5K 가 별개 short"
            " 로 식별. Gasket 은 별도 Matl_Std 필드 없음 — std 필터링은 Class_Define"
            " 의 std 로 처리 (별도 작업)."
        ),
        data_type="string (short code; ASTM 은 NNN# 형식, JIS/KS 는 prefix+NK 형식)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Gasket_Group.Rating 옵션 (closed set, 20개)."
        ),
        unique=None,
        relations=[
            "Flange_Group.Rating 과 옵션 풀 동일 — gasket 은 flange 와 짝",
            "Gasket_Type 과 호환 관행: RTJ gasket 은 600#+ 고압이 흔함 — 강제 검증"
            " 없음, 사용자 판단",
            "Class_Define.std 와 std-aware 필터링 (별도 작업)",
            "PMS description 에 합성 (예: 'GASKET SW SS316+Graphite RF 150#')",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + Class std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Facing",
        meaning=(
            "Gasket 의 접촉면(face) 형식. Flange_Group.Facing 의 일반 짝 3개만:"
            " RF (Raised Face — 가장 흔함),"
            " FF (Flat Face — cast iron flange 짝),"
            " RTJ (Ring Type Joint — 고압용; Gasket_Type=RTJ 와 짝)."
            " MF/FM/TG/LM/LF/SM/SF 등 male/female 짝은 gasket 측에서 별도 facing"
            " 표기가 의미 없어 제외 (현재 미고려)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Gasket_Group.Facing 옵션 (closed set, 3개)."
        ),
        unique=None,
        relations=[
            "Flange_Group.Facing 과 짝 — flange face 와 gasket face 는 일치해야"
            " 정합 (별도 검증 영역)",
            "Gasket_Type 과 호환 관행: Gasket_Type=RTJ 일 때 Facing=RTJ — 강제"
            " 검증은 별도 작업",
            "PMS description 에 합성 (facing 토큰)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Thickness",
        meaning=(
            "Gasket 두께. 콤보박스 (closed set, 4개): 1.5T / 3.0T / 4.5T / 6.0T"
            " (mm). 'T' 접미사는 thickness 의 산업 관행 표기."
            " Gasket_Type 별 일반 두께 관행:"
            " SHEET 는 3.0T/4.5T 흔함, SW 는 4.5T 표준, RTJ 는 ring 직경으로 결정"
            " 되므로 thickness 의미 작음 — 그래도 일관성 위해 채움."
            " 0.5/0.8/1.0/2.0/5.0mm 등은 현재 미고려."
        ),
        data_type="string (short code; '1.5T' / '3.0T' / '4.5T' / '6.0T')",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Gasket_Group.Thickness 옵션"
            " (closed set, 4개)."
        ),
        unique=None,
        relations=[
            "Gasket_Type 과 호환 관행 (위 의미 참조) — 강제 검증 없음",
            "PMS description 에 합성 (thickness 토큰)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit="mm (T 접미사로 표기)",
    ),
    FieldDefinition(
        name="Option_Code",
        meaning=(
            "Item_Code 변종/옵션 식별자. Pipe_Group.Option_Code 와 의미·형식"
            " 동일 — 3자리 숫자 텍스트, '001' = 해당 Class · Gasket_Group 의 표준형."
        ),
        data_type="string (3자리 0-9 숫자 텍스트; e.g. '001')",
        required=True,
        format_constraint=(
            "정규식 ^\\d{3}$. data/field_values.json 의 Gasket_Group.Option_Code"
            " 옵션 (closed set). 현재 '001' 한 개만 등록."
        ),
        unique=(
            "(Class_Name, Option_Code) 가 Gasket_Group 시트 안에서 유일."
            " 다른 시트의 Option_Code 와는 독립."
        ),
        relations=[
            "(Class_Name, Option_Code) 가 Gasket_Group 행의 자연 키",
            "Pipe_Group.Option_Code 와 동일 패턴",
        ],
        validation_location=(
            "Pipe_Group.Option_Code 와 동일 패턴 — 검증 모두 현재 미구현."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Remarks",
        meaning=(
            "행 단위 비고/설명 자유 텍스트. Pipe_Group.Remarks 와 의미·동작 동일."
        ),
        data_type="string (자유 텍스트, 빈 값 허용)",
        required=False,
        format_constraint=(
            "형식 강제 없음 — data/field_values.json 의 _meta.free_input_fields"
            " 에 'Remarks' 명시 (모든 시트 공통)."
        ),
        unique=None,
        relations=[
            "PMS description 합성의 마지막 토큰 — Pipe_Group.Remarks 와 동일 패턴",
        ],
        validation_location=(
            "검증 없음 (자유 입력). required 아님."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 자유 텍스트 입력 (Entry widget)"
        ),
        unit=None,
    ),
]


# ── Bolt_Group ─────────────────────────────────────────────────────────────────
#
# Bolt (flange 끼리, 또는 flange-equipment 결합용 체결재) — 한 행에 Bolt 와 Nut
# 두 component 의 정보를 담되, Nut 재질은 Bolt 를 따라간다.
# Item_Code 는 'B' (BOLT & NUT) 하나만 정의되어 있음; 변종은 Option_Code 로 처리.
#
# 다른 시트와 비교한 주요 특성:
#   - Bolt 재질: Bolt_Matl_Category/Std/Code 3컬럼. Nut 는 Nut_Type + Nut_Matl_Std
#     + Nut_Matl_Code. Nut designation 은 Bolt 와 다르며(B7↔2H) 독립 지정;
#     카테고리(탄소강계/SS계)만 Bolt 를 추종 — 큰 분류 일치 검증은 Phase 2-b.
#   - Bolt_Length_Table: size 별 bolt 길이를 별도 시트에 두고 키로 참조
#     · 옵션 풀은 닫힌 집합이 아니라 사용자 자유 — _meta.external_dropdown_sources
#       에 "TBD: separate length table file" 로 표기되어 있음.
#     · LT-A / LT-B 같은 표기를 사용자가 정함; 본 도메인 검증은 별도 작업.
#   - Bolt_Type / Nut_Type: 형식 구분
#     · Bolt_Type: Stud / Machine (Hex Cap Screw 등은 현재 미고려)
#     · Nut_Type: Hex / Heavy Hex (HHex)
#   - Matl_Std: ASTM/JIS/KS 3종 (Pipe/Flange 와 달리 EN 없음)
#     · 현재 옵션 풀에 EN 항목 없어 단순화. 추후 EN 추가 시 옵션 풀에만 추가.
#
# Bolt dia 단위 체계 (Metric vs Inch):
#   도메인적으로는 flange 표준이 결정:
#     - ASME B16.5 flange → bolt 직경 inch 고정 (ASME B18.31.2 / B18.2.1)
#       · "diameter of bolts and flange bolt holes" 만은 inch 단위로 명시되며,
#         metric bolt (B18.2.3.6M) 와의 혼용은 표준 부적합 (nonconformance).
#     - JIS B 2220 flange → bolt M-thread (metric)
#     - KS B 1503 flange → bolt M-thread (metric)
#   다만 PMS 운영상은 이 매핑을 코드로 강제 검증하지 않음 (도메인 결정):
#     · 사용자가 Bolt_Length_Table 에 자유롭게 inch 든 metric 이든 입력
#     · Bolt sheet 자체에는 dia system 컬럼이 없음 — std 와 system 간 종속 강제 X
#     · 이는 RefPMS 가 "데이터 입력 도구" 역할에 충실하고, bolt-flange 정합 검증은
#       사용자 책임으로 두는 정책 (별도 작업으로 확장 가능).
#
# Size 시스템:
#   - Size_From / Size_To 한 짝 (flange 의 NPS/DN 따라감 — 옵션 A)
#   - Bolt sheet 의 Size 는 flange size 범위와 의미·옵션 풀 동일 — 한 행이 어느
#     flange size 범위에 적용될지 명시.
#   - 실제 bolt 구경(inch/M-thread)은 Bolt_Length_Table 에서 size 별로 매핑.
#
# 미고려 항목 (추후 도메인 합의 시 확장):
#   - Bolt_Type: Hex Bolt (Hex Cap Screw), Square Head, Carriage 등
#   - Nut_Type: Square Nut, Coupling Nut, Lock Nut, Self-Locking 등
#   - Matl_Std: EN (예: EN ISO 898-1 Class 8.8, 10.9) — 현재 미등록
#   - Bolt-Nut 표준 짝 강제 (A193-B7 ↔ A194-2H 등) — 자유 조합으로 시작
#   - Bolt_Length_Table 의 시트 정의 자체 (별도 시트로 분리하는 작업)
#   - Coating / Plating (Hot-dip galvanized, Zinc, Xylan 등) — Remarks 로 우회
#   - Washer 사양 — 미고려

BOLT_GROUP_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="Class_Name",
        meaning=(
            "이 행이 소속될 Class 의 이름. Pipe_Group.Class_Name 과 의미·검증"
            " 모두 동일."
        ),
        data_type="string",
        required=True,
        format_constraint=(
            "공백 trim. Class_Define.Class_Name 행 집합 기준 일치 검사."
        ),
        unique=None,
        relations=[
            "Class_Define.Class_Name 으로 FK",
        ],
        validation_location=(
            "Pipe_Group.Class_Name 과 동일 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class_Define 행 목록)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Item_Code",
        meaning=(
            "Bolt_Group 의 component 종류 식별자. 현재 'B' (BOLT & NUT) 하나만"
            " 정의 — bolt 와 nut 를 한 set 로 묶어 한 component 로 취급."
            " Stud / Machine 의 형식 차이는 Item_Code 가 아니라 Bolt_Type 컬럼."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/item_code_db.json 의 Bolt_Group 행 (closed set, 현재 1개)."
        ),
        unique=None,
        relations=[
            "item_code_db.json Bolt_Group 의 code 값 중 하나 (FK)",
            "PMS description prefix 합성: B → BOLT & NUT",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set 옵션 강제)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — item_code_db 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size_From",
        meaning=(
            "NPS/DN size 범위의 하한. 의미는 'flange 의 NPS/DN 기준 적용 범위'"
            " — bolt 자체의 구경(inch/M-thread) 이 아니라 flange 와 연동되는 size."
            " Pipe_Group.Size_From 과 같은 catalog 사용."
            " 실제 bolt 구경은 Bolt_Length_Table 에서 size 별로 매핑 (그 매핑이"
            " inch 든 metric 이든 PMS 는 강제하지 않음)."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size_From <= Size_To 강제 (행 단위 검증, 별도 작업으로 구현 예정)."
        ),
        unique=None,
        relations=[
            "Class_Define.Size_From / Size_To 범위 안",
            "Flange_Group.Size1_From / Size1_To 와 의미적 짝 (flange 가 결정)",
            "Bolt_Length_Table 의 row 와 매핑 (size → 실제 bolt 구경 + 길이)",
        ],
        validation_location=(
            "Pipe_Group.Size_From 패턴 — component_row_size_pair_errors 확장 필요."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size_To",
        meaning=(
            "NPS/DN size 범위의 상한. Size_From 의 상한 짝."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size_From <= Size_To 강제."
        ),
        unique=None,
        relations=[
            "(Size_From, Size_To) 의 상한",
        ],
        validation_location=(
            "Pipe_Group.Size_To 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Bolt_Type",
        meaning=(
            "Bolt 의 형식 분류. 2종:"
            " Stud (Stud Bolt — 양 끝 나사 가공, flange 결합에 가장 흔함),"
            " Machine (Machine Bolt — Hex 머리 + 한 끝 나사)."
            " Hex Cap Screw / Square Head 등은 현재 미고려."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Bolt_Group.Bolt_Type 옵션"
            " (closed set, 2개)."
        ),
        unique=None,
        relations=[
            "Bolt_Matl_Code 와 호환 관행: Stud 는 A193-B7 등 stud-grade 흔함,"
            " Machine 은 A307-B 등 — 강제 검증 없음, 사용자 판단",
            "Nut_Type 과 짝: Stud 는 Heavy Hex Nut 짝이 일반적, Machine 은 Hex"
            " Nut — 강제 검증 없음",
            "PMS description 에 합성 (bolt type 토큰)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Bolt_Matl_Category",
        meaning=(
            "Bolt 재질의 대분류 카테고리. 4개 (CS/LTCS/AS/SS) — Pipe/Flange 의"
            " 7개보다 좁음 (bolt 용 재질이 그만큼 좁기 때문)."
            " DSS/SDSS/Ni-Alloy/Cu-Alloy 는 bolt 영역에서 거의 사용 안 함 — 미고려."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Bolt_Group.Bolt_Matl_Category 옵션"
            " (closed set, 4개)."
        ),
        unique=None,
        relations=[
            "Bolt_Matl_Std / Bolt_Matl_Code 와 종속 체인 (Pipe_Group 패턴 동일)",
            "Nut 재질은 Bolt 를 추종 (Nut 전용 category/code 입력 없음)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Bolt_Matl_Std",
        meaning=(
            "Bolt 재질 표준 발행 기관. 3개 (ASTM/JIS/KS) — Pipe/Flange 의 4개에서"
            " EN 제외. 추후 EN ISO 898-1 등록 시 확장."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Bolt_Group.Bolt_Matl_Std 옵션"
            " (closed set, 3개)."
        ),
        unique=None,
        relations=[
            "Bolt_Matl_Code 의 std 키와 일치",
            "Nut_Matl_Std 와는 독립 — 자유 조합",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Bolt_Matl_Code",
        meaning=(
            "Bolt 의 구체 재질 규격 코드. std-aware 필드 — 표준별 옵션이 다름."
            " ASTM (5개): A307-B (CS), A193-B7/B16 (Cr-Mo alloy steel Stud),"
            " A320-L7 (저온 Stud, LTCS 로 분류), A193-B8 (SS304 Stud)."
            " JIS (1개): SCM435 (Cr-Mo, AS)."
            " 'M' suffix 변종(B7M/L7M/B8M)은 도메인 합의로 제외. KS/EN 추후 추가."
        ),
        data_type="string (short code; e.g. A193-B7 / SCM435)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Bolt_Group.Bolt_Matl_Code 옵션"
            " (closed set, 6개). KS/EN 항목은 추후 추가."
        ),
        unique=None,
        relations=[
            "Bolt_Matl_Std (FK, std 필터) 와 Bolt_Matl_Category (code_category"
            "_consistency 검증) 에 종속 — Pipe_Group.Matl_Code 와 동일 패턴",
            "Bolt_Type 과 호환 관행: Stud-grade (B7 등) 와 Machine-grade (A307 등)"
            " 구분 — 강제 검증 없음",
            "Nut 는 Nut_Matl_Code 로 독립 지정 — 카테고리(탄소강계/SS계)는 Bolt 를"
            " 추종하나 designation 은 다름 (예: B7 ↔ 2H). 큰 분류 일치 검증은 별도",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터);"
            " 저장 시 Bolt_Matl_Code↔Bolt_Matl_Category 일관성 검증."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중"
            " Bolt_Matl_Std 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Nut_Type",
        meaning=(
            "Nut 의 형식 분류. 2종:"
            " Hex (Hex Nut — 일반 6각 너트),"
            " HHex (Heavy Hex Nut — 두꺼운 6각 너트, stud 짝)."
            " Square / Coupling / Lock / Self-Locking 등은 현재 미고려."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Bolt_Group.Nut_Type 옵션 (closed set, 2개)."
        ),
        unique=None,
        relations=[
            "Bolt_Type 과 호환 관행: Stud 는 HHex 짝이 일반적, Machine 은 Hex —"
            " 강제 검증 없음",
            "PMS description 에 합성 (nut type 토큰)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Nut_Matl_Std",
        meaning=(
            "Nut 재질 표준 발행 기관. Bolt_Matl_Std 와 옵션 풀 동일 (3개:"
            " ASTM/JIS/KS). Nut_Matl_Code 를 std 로 필터링한다."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Bolt_Group.Nut_Matl_Std 옵션"
            " (closed set, 3개)."
        ),
        unique=None,
        relations=[
            "Nut_Matl_Code 와 종속 (std 키 일치 필터 — Bolt_Matl_Std 패턴 동일)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Nut_Matl_Code",
        meaning=(
            "Nut 의 구체 재질 규격 코드 (designation). Bolt 와 독립 지정 —"
            " 카테고리(탄소강계/SS계)는 Bolt 를 추종하나 designation 은 다르다"
            " (표준 짝: A193-B7 ↔ A194-2H, A320-L7 ↔ A194-7, A193-B8 ↔ A194-8)."
            " ASTM (3개): A194-2H (CS, B7/B16 짝), A194-7 (LTCS, L7 짝),"
            " A194-8 (SS304, B8 짝). 'M' 변종(2HM/8M)은 도메인 합의로 제외."
            " PMS description 에 Bolt_Matl_Code 와 '/' 로 병기 (예: 'B7 / 2H')."
        ),
        data_type="string (short code; e.g. A194-2H)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Bolt_Group.Nut_Matl_Code 옵션"
            " (closed set, 3개). std 키로 Nut_Matl_Std 필터. KS/EN 추후 추가."
        ),
        unique=None,
        relations=[
            "Nut_Matl_Std (FK, std 필터) 에 종속 — Bolt_Matl_Code 와 동일 패턴",
            "카테고리는 Bolt 추종 (탄소강계 볼트엔 탄소강계 너트, SS 엔 SS) —"
            " 큰 분류 일치 검증은 별도 작업(Phase 2-b)",
            "PMS description 에 Bolt_Matl_Code 와 병기",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + Nut_Matl_Std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중"
            " Nut_Matl_Std 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Bolt_Length_Table",
        meaning=(
            "Bolt 길이 매핑 테이블의 식별자 (예: 'LT-A', 'LT-B'). 별도 시트에서"
            " 정의되며, 한 row 가 (NPS/DN size, flange rating, facing, gasket 종류"
            " 등) → 실제 bolt 구경 (inch 또는 M-thread) + bolt 길이 (mm/inch) 로"
            " 매핑."
            " 실제 bolt 구경 단위 (inch vs M-thread) 는 이 table 에서 결정 — Bolt"
            " sheet 자체에는 단위 체계 강제 없음."
            " 현재는 자유 텍스트 또는 추후 외부 시트 reference (별도 작업)."
            " _meta.external_dropdown_sources 에 'TBD: separate length table file'"
            " 로 표기됨."
        ),
        data_type="string (table identifier; e.g. 'LT-A')",
        required=True,
        format_constraint=(
            "현재 형식 강제 없음 — 사용자 자유 텍스트. 추후 외부 시트 reference"
            " 로 closed set 화 예정."
        ),
        unique=None,
        relations=[
            "(외부) Bolt_Length_Table 시트 — table_id → size/dia/length 매핑",
            "Class_Define.std 와 Bolt_Length_Table 의 단위 체계 (inch/metric)"
            " 정합은 사용자 책임 (RefPMS 는 강제 검증 안 함)",
            "PMS description 합성 시 size 별 bolt 길이 lookup 의 키",
        ],
        validation_location=(
            "현재 미구현 — 자유 텍스트 입력."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 자유 텍스트 입력 (Entry widget)."
            " 추후 외부 시트 reference 콤보로 전환 예정."
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Option_Code",
        meaning=(
            "Item_Code 변종/옵션 식별자. Pipe_Group.Option_Code 와 의미·형식"
            " 동일 — 3자리 숫자 텍스트, '001' = 해당 Class · Bolt_Group 의 표준형."
        ),
        data_type="string (3자리 0-9 숫자 텍스트; e.g. '001')",
        required=True,
        format_constraint=(
            "정규식 ^\\d{3}$. data/field_values.json 의 Bolt_Group.Option_Code"
            " 옵션 (closed set). 현재 '001' 한 개만 등록."
        ),
        unique=(
            "(Class_Name, Option_Code) 가 Bolt_Group 시트 안에서 유일."
            " 다른 시트의 Option_Code 와는 독립."
        ),
        relations=[
            "(Class_Name, Option_Code) 가 Bolt_Group 행의 자연 키",
            "Pipe_Group.Option_Code 와 동일 패턴",
        ],
        validation_location=(
            "Pipe_Group.Option_Code 와 동일 패턴 — 검증 모두 현재 미구현."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Remarks",
        meaning=(
            "행 단위 비고/설명 자유 텍스트. Pipe_Group.Remarks 와 의미·동작 동일."
            " Bolt-Nut 표준 짝 (예: 'A193-B7 ↔ A194-2H'), coating 사양 (예: 'HDG"
            " Class C'), 적용 범위 부연 설명 등을 자유 입력."
        ),
        data_type="string (자유 텍스트, 빈 값 허용)",
        required=False,
        format_constraint=(
            "형식 강제 없음 — data/field_values.json 의 _meta.free_input_fields"
            " 에 'Remarks' 명시 (모든 시트 공통)."
        ),
        unique=None,
        relations=[
            "PMS description 합성의 마지막 토큰 — Pipe_Group.Remarks 와 동일 패턴",
        ],
        validation_location=(
            "검증 없음 (자유 입력). required 아님."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 자유 텍스트 입력 (Entry widget)"
        ),
        unit=None,
    ),
]


# ── Gate_Valve_Group ───────────────────────────────────────────────────────────
#
# Gate Valve (직선형 흐름의 차단·개방 전용 valve) — Valve 6종 중 첫 번째 시트.
# 다른 Valve 시트 (Globe/Check/Ball/Butterfly/Plug) 의 기본 컬럼 패턴 (Class/Item/
# Size1 짝/Body Matl/Trim/Seat/Rating/End/Bonnet/Operation/Option/Remarks) 을
# 공유하되, Gate 고유 필드 Wedge_Type 가 추가됨.
#
# 다른 시트와 비교한 주요 특성:
#   - Body Matl_Code 는 cast grade (A216-WCB 등) — Pipe/Flange 의 forged grade
#     와 다른 옵션 풀. Cast valve body 가 일반.
#   - Trim_Matl 단일 컬럼: API 600 trim number 표준 세트를 재질조합 문자열로
#     저장 (seat/disc/stem 조합을 한 값으로 표현). Seat_Matl 전용 컬럼은 폐지.
#     Body 재질과 독립적으로 운영 조건 (corrosive / hardness) 따라 선택.
#   - Wedge_Type 는 Item_Code 분리 대신 컬럼화 — 도메인 관행상 Procurement
#     description 에 명시 안 하는 경우도 흔함 (forged=Solid, cast=Flexible 의
#     관습이 통용). 따라서 required=False, 빈 값 허용 + 옵션 풀 4종 (Solid/
#     Flexible/Split/TC).
#   - Bore (FB/RB) 컬럼 제거 — Gate Valve 는 거의 Full Bore 가 표준. 특수한 RB
#     Gate 는 별도 명시 필요 시 Remarks 로 우회.
#   - Stem_Type (OS&Y/NRS/Rising Stem) 컬럼 없음 — Bonnet_Stem / Operation 으로
#     대부분의 구조 정보가 표현됨.
#   - Size 시스템: Size1_From / Size1_To 한 짝 (Flange Size1 패턴; Valve 는
#     Reducing 없음).
#   - Rating: std-aware (ASTM 7 + JIS 7 + KS 7 = 21개; ASTM 에 800# 추가) —
#     ASTM 기준 표준은 ASME B16.5 (Flange) 가 아닌 ASME B16.34 (Valve).
#   - End_Type: BW/SW/TH/FLG 4종.
#   - Bonnet_Stem: BB OS&Y / BB NRS / BB ISRS / WB OS&Y / PSB OS&Y / SB ISRS /
#     SB NRS 7조합 (bonnet + stem 통합).
#   - Operation: Manual (Handwheel) / Lever / Wrench / Gear / Chain 5종 — Motor
#     / Pneumatic / Hydraulic 등 actuator 류는 현재 미고려 (별도 actuator 시트
#     로 분리 검토).
#
# 미고려 항목 (추후 도메인 합의 시 확장):
#   - Stem_Type 컬럼
#   - Bore 컬럼 (FB/RB) — Gate 에서는 의미 작음, Ball/Plug 에서 의미 큼
#   - Actuator 종류 (Motor/Pneumatic/Hydraulic) — 별도 actuator 시트
#   - Wedge_Type 'Parallel Slide' (Gate 의 특수 형식)
#   - Bypass valve 정보 (대구경 Gate 의 보조 valve)
#   - Item_Code 분리: Cast vs Forged (VA / VAF) 등 — 현재 VA 하나로 유지
#
# 다른 Valve 시트와의 공통 구조:
#   - 15 필드 (현재 Gate; Seat_Matl 폐지). 다른 Valve (Globe/Check 등) 는 valve
#     별 고유 컬럼 (Disc_Type / Plug_Type 등) 으로 비슷한 길이.
#   - Class_Name → Item_Code → Size1 → Body Matl → Trim → Rating →
#     End_Type → Bonnet_Stem → (valve 고유: Wedge_Type) → Operation →
#     Option_Code → Remarks 순서.

GATE_VALVE_GROUP_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="Class_Name",
        meaning=(
            "이 행이 소속될 Class 의 이름. Pipe_Group.Class_Name 과 의미·검증"
            " 모두 동일."
        ),
        data_type="string",
        required=True,
        format_constraint=(
            "공백 trim. Class_Define.Class_Name 행 집합 기준 일치 검사."
        ),
        unique=None,
        relations=[
            "Class_Define.Class_Name 으로 FK",
        ],
        validation_location=(
            "Pipe_Group.Class_Name 과 동일 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class_Define 행 목록)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Item_Code",
        meaning=(
            "Gate_Valve_Group 의 component 종류 식별자. 현재 'VA' (GATE VALVE)"
            " 하나만 정의 — Wedge type 의 차이 (Solid/Flexible 등) 는 Wedge_Type"
            " 컬럼으로 구분. Cast vs Forged 의 Item_Code 분리는 현재 미고려."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/item_code_db.json 의 Gate_Valve_Group 행 (closed set, 현재 1개)."
        ),
        unique=None,
        relations=[
            "item_code_db.json Gate_Valve_Group 의 code 값 중 하나 (FK)",
            "PMS description prefix 합성: VA → GATE VALVE",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set 옵션 강제)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — item_code_db 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size1_From",
        meaning=(
            "NPS/DN size 범위의 하한. Flange_Group.Size1_From 과 의미 동일."
            " Valve 는 Reducing 없음 — 단일 size 짝 (Size1_From/Size1_To) 사용."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size1_From <= Size1_To 강제 (행 단위 검증, 별도 작업)."
        ),
        unique=None,
        relations=[
            "Class_Define.Size_From / Size_To 범위 안",
        ],
        validation_location=(
            "Pipe_Group.Size_From 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size1_To",
        meaning=(
            "NPS/DN size 범위의 상한. Size1_From 의 상한 짝."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size1_From <= Size1_To 강제."
        ),
        unique=None,
        relations=[
            "(Size1_From, Size1_To) 의 상한",
        ],
        validation_location=(
            "Pipe_Group.Size_To 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Category",
        meaning=(
            "Valve body 재질의 대분류 카테고리. Pipe/Flange 와 동일 7개"
            " (CS/LTCS/AS/SS/DSS/SDSS/Ni-Alloy)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Gate_Valve_Group.Matl_Category 옵션"
            " (closed set, 7개)."
        ),
        unique=None,
        relations=[
            "Matl_Std / Matl_Code 와 종속 체인 (Pipe_Group 패턴 동일)",
            "Trim_Matl / Seat_Matl 과는 독립",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Std",
        meaning=(
            "Valve body 재질 표준 발행 기관. 4개 (ASTM/JIS/KS/EN)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Gate_Valve_Group.Matl_Std 옵션"
            " (closed set, 4개)."
        ),
        unique=None,
        relations=[
            "Matl_Code 의 std 키와 일치",
            "Rating 의 std 키와도 일치 — std-aware Rating 필터링",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Code",
        meaning=(
            "Valve body 의 구체 재질 규격 코드. **Cast grade** — Pipe/Flange/"
            "Fitting 의 forged grade 와 다른 옵션 풀."
            " ASTM (8): A216-WCB (CS Cast Body), A352-LCB/LCC (LTCS Cast),"
            " A351-CF8/CF8M (SS304/SS316 Cast), A217-WC1/WC6/WC9 (Cr-Mo Cast)."
            " JIS (2): SCS13A/SCS14A (SS304/SS316 Cast). KS/EN 항목은 추후."
        ),
        data_type="string (short code; e.g. A216-WCB / SCS13A)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Gate_Valve_Group.Matl_Code 옵션"
            " (closed set, 10개). KS/EN 항목은 추후 추가."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK), Matl_Category (의미적 정합) 와 함께 필터링",
            "Trim_Matl / Seat_Matl 과는 독립 (body 와 내부 부품 재질이 다름)",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중"
            " Matl_Std 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Trim_Matl",
        meaning=(
            "Valve trim 재질 조합. Seat / disc / stem 의 재질 세트를 하나의 값으로"
            " 표현하며, API 600 trim number 표준 세트(전 번호 수록)를 재질조합"
            " 문자열(short, 예: '13Cr+STL', 'F316', 'Alloy20+STL')로 저장한다."
            " Seat_Matl 전용 필드는 폐지 — trim 값 하나가 seat/disc/stem 조합을 담는다."
        ),
        data_type="string (재질조합 문자열)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Gate_Valve_Group.Trim_Matl 옵션"
            " (closed set, API 600 trim 전 번호; 현재 28개)."
        ),
        unique=None,
        relations=[
            "seat/disc/stem 재질을 단일 값으로 통합 (Seat_Matl 필드 대체)",
            "PMS description 의 trim token 에 그대로 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Rating",
        meaning=(
            "Valve 의 압력 등급. std-aware 필드 — ASTM 기준 표준은 ASME **B16.34**"
            " (Valve), Flange 의 ASME B16.5 와 구분."
            "\n - ASTM: 150# / 300# / 600# / 800# / 900# / 1500# / 2500#"
            " (800# 은 forged valve 용으로 추가)."
            "\n - JIS: 5K / 10K / 16K / 20K / 30K / 40K / 63K."
            "\n - KS: 5K / 10K / 16K / 20K / 30K / 40K / 63K."
        ),
        data_type="string (short code; ASTM NNN# 형식 / JIS·KS prefix+NK 형식)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Gate_Valve_Group.Rating 옵션"
            " (closed set, 21개 — 800# 포함)."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK) — std-aware 필터링의 1차 게이트",
            "Flange_Group.Rating 의 옵션 풀과 동일 — flange 와 valve 가 같은"
            " rating 체계를 공유",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중 Matl_Std"
            " 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="End_Type",
        meaning=(
            "Valve 단부 (end connection) 형식. 6종:"
            " BW (Butt Weld), SW (Socket Weld), TH (Threaded),"
            " FLGD RF / FLGD FF / FLGD RTJ (Flanged — facing 별: Raised Face /"
            " Flat Face / Ring Type Joint)."
            " Flange facing 을 End_Type 토큰에 포함한다. Mechanical joint /"
            " Grooved 등은 현재 미고려."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Gate_Valve_Group.End_Type 옵션"
            " (closed set, 6개)."
        ),
        unique=None,
        relations=[
            "End_Type 이 FLGD* 일 때 Rating 이 상대 flange 와 짝이 되어야 정합"
            " (facing 은 End_Type 토큰에 포함). (별도 검증 영역)",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Bonnet_Stem",
        meaning=(
            "Valve bonnet (body 상단 덮개) 형식과 stem 구동 방식의 통합 분류."
            " 현실 조합 7개: BB OS&Y / BB NRS / BB ISRS / WB OS&Y / PSB OS&Y /"
            " SB ISRS / SB NRS."
            " 본넷 BB=Bolted · WB=Welded · PSB=Pressure-Sealed · SB=Screwed;"
            " stem OS&Y=Outside Screw & Yoke · NRS=Non-Rising Stem ·"
            " ISRS=Inside Screw Rising Stem."
            " 비현실 조합(WB/PSB 의 비-OS&Y 등)은 제외."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Gate_Valve_Group.Bonnet_Stem 옵션"
            " (closed set, 7개)."
        ),
        unique=None,
        relations=[
            "Rating 과 호환 관행: PSB 는 600#+ 고압이 흔함 — 강제 검증 없음",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Wedge_Type",
        meaning=(
            "Gate Valve 의 wedge (차단부) 형식. **Gate Valve 고유 컬럼** — 다른"
            " Valve 시트엔 없음. 4종:"
            " Solid (Solid Wedge — forged valve 의 통상), Flexible (Flexible"
            " Wedge — cast valve 의 통상), Split (Split Wedge), TC (Through"
            " Conduit / Slab — pipeline 용)."
            " 빈 값 허용 — Procurement description 에 명시 안 하는 관행이 흔함"
            " (forged=Solid, cast=Flexible 의 관습이 통용)."
        ),
        data_type="string (short code; 빈 값 허용)",
        required=False,
        format_constraint=(
            "data/field_values.json 의 Gate_Valve_Group.Wedge_Type 옵션"
            " (closed set, 4개 + 빈 값)."
        ),
        unique=None,
        relations=[
            "Matl_Code 와 호환 관행: forged grade 와 Solid, cast grade 와"
            " Flexible 이 통상 — 강제 검증 없음",
            "PMS description 에 합성 (빈 값이면 토큰 생략)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set, 빈 값 허용)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Operation",
        meaning=(
            "Valve 조작 방식. 5종:"
            " Manual (Handwheel — 가장 흔함),"
            " Lever (소구경 ball/butterfly 흔함; Gate 에선 드묾),"
            " Wrench (Wrench Operated), Gear (Gear Operated — 대구경),"
            " Chain (Chain Operated — 높은 위치)."
            " Motor / Pneumatic / Hydraulic 등 actuator 는 현재 미고려 (별도"
            " actuator 시트로 분리 검토)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Gate_Valve_Group.Operation 옵션"
            " (closed set, 5개)."
        ),
        unique=None,
        relations=[
            "Size1 과 호환 관행: 대구경 (8\"+) 은 Gear/Chain 이 흔함 — 강제 검증"
            " 없음",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Option_Code",
        meaning=(
            "Item_Code 변종/옵션 식별자. Pipe_Group.Option_Code 와 의미·형식"
            " 동일 — 3자리 숫자 텍스트, '001' = 해당 Class · Gate_Valve_Group"
            " 의 표준형."
        ),
        data_type="string (3자리 0-9 숫자 텍스트; e.g. '001')",
        required=True,
        format_constraint=(
            "정규식 ^\\d{3}$. data/field_values.json 의 Gate_Valve_Group.Option_Code"
            " 옵션 (closed set). 현재 '001' 한 개만 등록."
        ),
        unique=(
            "(Class_Name, Option_Code) 가 Gate_Valve_Group 시트 안에서 유일."
            " 다른 시트의 Option_Code 와는 독립."
        ),
        relations=[
            "(Class_Name, Option_Code) 가 Gate_Valve_Group 행의 자연 키",
            "Pipe_Group.Option_Code 와 동일 패턴",
        ],
        validation_location=(
            "Pipe_Group.Option_Code 와 동일 패턴 — 검증 모두 현재 미구현."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Remarks",
        meaning=(
            "행 단위 비고/설명 자유 텍스트. Pipe_Group.Remarks 와 의미·동작 동일."
            " Wedge type 의 도메인 관습 부연 (예: 'forged-Solid 통상'), Actuator"
            " 정보 (Motor / Pneumatic 등 — 별도 시트 미구현 단계 동안 우회),"
            " Bypass valve 정보 등을 자유 입력."
        ),
        data_type="string (자유 텍스트, 빈 값 허용)",
        required=False,
        format_constraint=(
            "형식 강제 없음 — data/field_values.json 의 _meta.free_input_fields"
            " 에 'Remarks' 명시 (모든 시트 공통)."
        ),
        unique=None,
        relations=[
            "PMS description 합성의 마지막 토큰 — Pipe_Group.Remarks 와 동일 패턴",
        ],
        validation_location=(
            "검증 없음 (자유 입력). required 아님."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 자유 텍스트 입력 (Entry widget)"
        ),
        unit=None,
    ),
]


# ── Globe_Valve_Group ──────────────────────────────────────────────────────────
#
# Globe Valve (구형 body 의 throttling/차단 valve) — Valve 6종 중 두 번째 시트.
# Gate_Valve_Group 의 15-필드 구조를 거의 그대로 공유 (Class/Item/Size1 짝/Body
# Matl/Trim/Rating/End/Bonnet/Operation/Option/Remarks; Seat_Matl 폐지) 하되,
# Gate 고유 Wedge_Type 자리에 Globe 고유 Disc_Type 가 들어감.
#
# Gate 와의 주요 차이:
#   - 고유 컬럼: Wedge_Type → Disc_Type (Plug / Conventional / Composition 3종
#     + 빈 값 허용). 헤더 위치도 다름 — Gate 는 Bonnet_Stem 뒤, Globe 는
#     Operation 뒤 (Option_Code 직전). 의미적으로 Operation 결정 후 disc 결정이
#     실무 흐름.
#   - Disc 옵션 풀 (도메인 표준 + 사용자 결정):
#       · Plug: 원통형 + tapered / rounded end 의 plug disc. Forged Globe (API
#         602) 의 표준. 큰 유량 + 고차압에 적합.
#       · Conventional: ball-shaped disc, 짧은 테이퍼 + flat seat 접촉. 저압
#         서비스의 일반.
#       · Composition: 비금속 (PTFE / graphite 등) insert ring 으로 tight
#         closure 구현. 고온고압 + erosion 저항 필요 시.
#       · (빈 값): Procurement Description 에 명시 안 하는 케이스 — forged 통상
#         Plug, cast 통상 Plug/Conventional 의 관습이 통용.
#     Needle disc 는 Globe 의 Disc_Type 가 아니라 별도 Needle_Valve_Group 시트
#     로 분리 예정 (사용자 결정 — needle valve 는 독립 valve type).
#   - Parabolic disc (throttling 정밀 제어용) 는 현재 옵션 풀에 미포함 — control
#     valve 영역에 가까운 특수 케이스로 추후 검토.
#
# Gate 와 동일한 부분:
#   - Body Matl_Code 는 cast grade (A216-WCB 등) — Pipe/Flange 의 forged grade
#     와 다른 옵션 풀.
#   - Trim_Matl 단일 컬럼 (API 600 trim 조합): Gate 와 동일 옵션 풀. Seat_Matl 폐지.
#   - Size 시스템: Size1_From / Size1_To 한 짝 (Reducing 없음).
#   - Rating: std-aware (ASTM 7 + JIS 7 + KS 7 = 21개; 800# 포함) — Gate 와
#     동일 옵션 풀 + std 키 부여. ASTM 기준 표준은 ASME B16.34.
#   - End_Type 4종, Bonnet_Stem 4종, Operation 5종.
#   - Stem_Type / Bore / Actuator 종류 컬럼 미고려 (Gate 와 동일 정책).
#
# 미고려 항목 (추후 도메인 합의 시 확장):
#   - Body pattern (T-pattern / Y-pattern / Angle) 컬럼 — 현재 Remarks 로 우회
#   - Stem_Type 컬럼
#   - Parabolic disc (control valve 영역)
#   - Actuator 종류 (Motor / Pneumatic / Hydraulic) — 별도 actuator 시트
#   - Item_Code 분리: Cast vs Forged (VB / VBF) 등 — 현재 VB 하나로 유지
#
# 다른 Valve 시트와의 공통 구조:
#   - 15 필드 (Gate 와 동일 길이; Seat_Matl 폐지). Disc_Type / Wedge_Type 같은
#     valve 고유 컬럼 자리가 시트별 1 ~ 2 개로 변경되는 패턴.
#   - Class_Name → Item_Code → Size1 → Body Matl → Trim → Rating →
#     End_Type → Bonnet_Stem → Operation → (Globe 고유: Disc_Type) →
#     Option_Code → Remarks 순서.

GLOBE_VALVE_GROUP_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="Class_Name",
        meaning=(
            "이 행이 소속될 Class 의 이름. Pipe_Group.Class_Name 과 의미·검증"
            " 모두 동일."
        ),
        data_type="string",
        required=True,
        format_constraint=(
            "공백 trim. Class_Define.Class_Name 행 집합 기준 일치 검사."
        ),
        unique=None,
        relations=[
            "Class_Define.Class_Name 으로 FK",
        ],
        validation_location=(
            "Pipe_Group.Class_Name 과 동일 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class_Define 행 목록)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Item_Code",
        meaning=(
            "Globe_Valve_Group 의 component 종류 식별자. 현재 'VB' (GLOBE VALVE)"
            " 하나만 정의 — Disc 종류 차이 (Plug/Conventional/Composition) 는"
            " Disc_Type 컬럼으로 구분. Cast vs Forged 의 Item_Code 분리는 현재"
            " 미고려."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/item_code_db.json 의 Globe_Valve_Group 행 (closed set, 현재"
            " 1개)."
        ),
        unique=None,
        relations=[
            "item_code_db.json Globe_Valve_Group 의 code 값 중 하나 (FK)",
            "PMS description prefix 합성: VB → GLOBE VALVE",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set 옵션 강제)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — item_code_db 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size1_From",
        meaning=(
            "NPS/DN size 범위의 하한. Gate_Valve_Group.Size1_From 과 동일 의미."
            " Valve 는 Reducing 없음 — 단일 size 짝 (Size1_From/Size1_To) 사용."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size1_From <= Size1_To 강제 (행 단위 검증, 별도 작업)."
        ),
        unique=None,
        relations=[
            "Class_Define.Size_From / Size_To 범위 안",
        ],
        validation_location=(
            "Pipe_Group.Size_From 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size1_To",
        meaning=(
            "NPS/DN size 범위의 상한. Size1_From 의 상한 짝."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size1_From <= Size1_To 강제."
        ),
        unique=None,
        relations=[
            "(Size1_From, Size1_To) 의 상한",
        ],
        validation_location=(
            "Pipe_Group.Size_To 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Category",
        meaning=(
            "Valve body 재질의 대분류 카테고리. Gate_Valve_Group 과 동일 7개"
            " (CS/LTCS/AS/SS/DSS/SDSS/Ni-Alloy)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Globe_Valve_Group.Matl_Category 옵션"
            " (closed set, 7개)."
        ),
        unique=None,
        relations=[
            "Matl_Std / Matl_Code 와 종속 체인 (Pipe_Group 패턴 동일)",
            "Trim_Matl / Seat_Matl 과는 독립",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Std",
        meaning=(
            "Valve body 재질 표준 발행 기관. 4개 (ASTM/JIS/KS/EN)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Globe_Valve_Group.Matl_Std 옵션"
            " (closed set, 4개)."
        ),
        unique=None,
        relations=[
            "Matl_Code 의 std 키와 일치",
            "Rating 의 std 키와도 일치 — std-aware Rating 필터링",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Code",
        meaning=(
            "Valve body 의 구체 재질 규격 코드. **Cast grade** — Pipe/Flange/"
            "Fitting 의 forged grade 와 다른 옵션 풀, Gate_Valve_Group 과 동일"
            " 옵션. ASTM (8): A216-WCB (CS Cast Body), A352-LCB/LCC (LTCS Cast),"
            " A351-CF8/CF8M (SS304/SS316 Cast), A217-WC1/WC6/WC9 (Cr-Mo Cast)."
            " JIS (2): SCS13A/SCS14A (SS304/SS316 Cast). KS/EN 항목은 추후."
        ),
        data_type="string (short code; e.g. A216-WCB / SCS13A)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Globe_Valve_Group.Matl_Code 옵션"
            " (closed set, 10개). KS/EN 항목은 추후 추가."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK), Matl_Category (의미적 정합) 와 함께 필터링",
            "Trim_Matl / Seat_Matl 과는 독립 (body 와 내부 부품 재질이 다름)",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중"
            " Matl_Std 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Trim_Matl",
        meaning=(
            "Valve trim 재질 조합 — seat/disc/stem 재질 세트를 하나의 값으로 표현."
            " API 600 trim number 표준 세트(전 번호)를 재질조합 문자열(short)로"
            " 저장. Gate 와 동일 옵션 풀. Seat_Matl 전용 필드는 폐지."
        ),
        data_type="string (재질조합 문자열)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Globe_Valve_Group.Trim_Matl 옵션"
            " (closed set, API 600 trim 전 번호; 현재 28개)."
        ),
        unique=None,
        relations=[
            "seat/disc/stem 재질을 단일 값으로 통합 (Seat_Matl 필드 대체)",
            "PMS description 의 trim token 에 그대로 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Rating",
        meaning=(
            "Valve 의 압력 등급. std-aware 필드 — Gate 와 옵션 풀 동일,"
            " ASTM 기준 표준은 ASME **B16.34** (Valve)."
            "\n - ASTM: 150# / 300# / 600# / 800# / 900# / 1500# / 2500#."
            "\n - JIS: 5K / 10K / 16K / 20K / 30K / 40K / 63K."
            "\n - KS: 5K / 10K / 16K / 20K / 30K / 40K / 63K."
        ),
        data_type="string (short code; ASTM NNN# 형식 / JIS·KS prefix+NK 형식)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Globe_Valve_Group.Rating 옵션"
            " (closed set, 21개 — 800# 포함)."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK) — std-aware 필터링의 1차 게이트",
            "Flange_Group.Rating / Gate_Valve_Group.Rating 과 옵션 풀 동일",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중 Matl_Std"
            " 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="End_Type",
        meaning=(
            "Valve 단부 (end connection) 형식. 6종:"
            " BW (Butt Weld), SW (Socket Weld), TH (Threaded),"
            " FLGD RF / FLGD FF / FLGD RTJ (Flanged — facing 별: Raised Face /"
            " Flat Face / Ring Type Joint)."
            " Flange facing 을 End_Type 토큰에 포함한다. Mechanical joint /"
            " Grooved 등은 현재 미고려."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Globe_Valve_Group.End_Type 옵션"
            " (closed set, 6개)."
        ),
        unique=None,
        relations=[
            "End_Type 이 FLGD* 일 때 Rating 이 상대 flange 와 짝이 되어야 정합"
            " (facing 은 End_Type 토큰에 포함). (별도 검증 영역)",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Bonnet_Stem",
        meaning=(
            "Valve bonnet (body 상단 덮개) 형식과 stem 구동 방식의 통합 분류."
            " 현실 조합 7개: BB OS&Y / BB NRS / BB ISRS / WB OS&Y / PSB OS&Y /"
            " SB ISRS / SB NRS."
            " 본넷 BB=Bolted · WB=Welded · PSB=Pressure-Sealed · SB=Screwed;"
            " stem OS&Y=Outside Screw & Yoke · NRS=Non-Rising Stem ·"
            " ISRS=Inside Screw Rising Stem."
            " 비현실 조합(WB/PSB 의 비-OS&Y 등)은 제외."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Globe_Valve_Group.Bonnet_Stem 옵션"
            " (closed set, 7개)."
        ),
        unique=None,
        relations=[
            "Rating 과 호환 관행: PSB 는 600#+ 고압이 흔함 — 강제 검증 없음",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Operation",
        meaning=(
            "Valve 조작 방식. 5종:"
            " Manual (Handwheel — 가장 흔함),"
            " Lever (Globe 에선 드묾), Wrench (Wrench Operated),"
            " Gear (Gear Operated — 대구경), Chain (Chain Operated — 높은 위치)."
            " Motor / Pneumatic / Hydraulic 등 actuator 는 현재 미고려 (별도"
            " actuator 시트로 분리 검토)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Globe_Valve_Group.Operation 옵션"
            " (closed set, 5개)."
        ),
        unique=None,
        relations=[
            "Size1 과 호환 관행: 대구경 (8\"+) 은 Gear/Chain 이 흔함 — 강제 검증"
            " 없음",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Disc_Type",
        meaning=(
            "Globe Valve 의 disc (차단·throttling 부품) 형식. **Globe Valve 고유"
            " 컬럼** — Gate 의 Wedge_Type 자리에 대응. 3종:"
            " Plug (Plug Disc — Forged Globe / API 602 표준),"
            " Conventional (Ball-shaped disc — 저압 일반),"
            " Composition (비금속 insert ring, tight closure — 고온고압)."
            " 빈 값 허용 — Procurement description 에 명시 안 하는 관행이 흔함"
            " (forged=Plug, cast=Plug/Conventional 의 관습이 통용)."
            " Needle disc 는 Globe 의 Disc_Type 가 아니라 별도 Needle_Valve_Group"
            " 시트로 분리 예정. Parabolic disc 는 control valve 영역으로 추후"
            " 검토."
        ),
        data_type="string (short code; 빈 값 허용)",
        required=False,
        format_constraint=(
            "data/field_values.json 의 Globe_Valve_Group.Disc_Type 옵션"
            " (closed set, 3개 + 빈 값)."
        ),
        unique=None,
        relations=[
            "Matl_Code 와 호환 관행: forged grade 와 Plug, cast grade 와"
            " Plug/Conventional 가 통상 — 강제 검증 없음",
            "PMS description 에 합성 (빈 값이면 토큰 생략)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set, 빈 값 허용)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Option_Code",
        meaning=(
            "Item_Code 변종/옵션 식별자. Pipe_Group.Option_Code 와 의미·형식"
            " 동일 — 3자리 숫자 텍스트, '001' = 해당 Class · Globe_Valve_Group"
            " 의 표준형."
        ),
        data_type="string (3자리 0-9 숫자 텍스트; e.g. '001')",
        required=True,
        format_constraint=(
            "정규식 ^\\d{3}$. data/field_values.json 의 Globe_Valve_Group.Option_Code"
            " 옵션 (closed set). 현재 '001' 한 개만 등록."
        ),
        unique=(
            "(Class_Name, Option_Code) 가 Globe_Valve_Group 시트 안에서 유일."
            " 다른 시트의 Option_Code 와는 독립."
        ),
        relations=[
            "(Class_Name, Option_Code) 가 Globe_Valve_Group 행의 자연 키",
            "Pipe_Group.Option_Code 와 동일 패턴",
        ],
        validation_location=(
            "Pipe_Group.Option_Code 와 동일 패턴 — 검증 모두 현재 미구현."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Remarks",
        meaning=(
            "행 단위 비고/설명 자유 텍스트. Pipe_Group.Remarks 와 의미·동작 동일."
            " Body pattern (T-pattern / Y-pattern / Angle 등 — 별도 컬럼 미구현"
            " 단계 동안 우회), Actuator 정보 (Motor / Pneumatic 등), Trim/Seat"
            " 호환 부연 설명 등을 자유 입력."
        ),
        data_type="string (자유 텍스트, 빈 값 허용)",
        required=False,
        format_constraint=(
            "형식 강제 없음 — data/field_values.json 의 _meta.free_input_fields"
            " 에 'Remarks' 명시 (모든 시트 공통)."
        ),
        unique=None,
        relations=[
            "PMS description 합성의 마지막 토큰 — Pipe_Group.Remarks 와 동일 패턴",
        ],
        validation_location=(
            "검증 없음 (자유 입력). required 아님."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 자유 텍스트 입력 (Entry widget)"
        ),
        unit=None,
    ),
]


# ── Check_Valve_Group ──────────────────────────────────────────────────────────
#
# Check Valve (역류 방지 valve) — Valve 6종 중 세 번째 시트.
# **자동 동작** (역류 압력으로 disc 가 seat 에 안착) 이라는 점이 Gate/Globe 와의
# 본질적 차이. 결과적으로 Bonnet_Stem / Operation 컬럼이 **없음** — 헤더 14개로
# Gate/Globe (16개) 보다 2개 적음.
#
# Gate/Globe 와의 주요 차이:
#   - 자동 동작: Bonnet_Stem 없음 (Check valve 는 통상 cover/bonnet 구분 약함),
#     Operation 없음 (handwheel/lever 등 조작부 없음 — 역류 시 자동 닫힘).
#   - 헤더 길이: 13 필드 (Class/Item/Size1 짝/Body Matl/Trim/Rating/End/
#     Disc_Type/Option/Remarks; Seat_Matl 폐지).
#   - Disc_Type 옵션 풀 (도메인 표준 + 사용자 결정):
#       · Swing: hinge 회전 disc, 2\"+ 대구경 표준. API 6D / ASME B16.34.
#       · Lift: 수직 lift, gravity / 압력 의존. **Piston check 변종 포함**
#         (Piston = lift + spring-loaded + piston-guided cylinder; 별도 컬럼
#         미고려, Remarks 우회).
#       · Tilting: 대구경 빠른 응답, water hammer 방지.
#       · Dual: Dual Plate (wafer / lug body, spring-loaded 2-disc). API 594.
#       · Ball: 볼이 disc 역할. 소구경, 점성 유체.
#       · (빈 값): Procurement Description 에 명시 안 하는 케이스.
#   - 도메인 노트: 기존 옵션 'Wafer' 제거 — Wafer 는 disc type 이 아니라 **body
#     type** (face-to-face short, between flanges). Single Plate 도 별도 disc
#     type 이 아닌 Swing + Wafer body 의 약칭으로 보아 미포함.
#
# Gate/Globe 와 동일한 부분:
#   - Body Matl_Code 는 cast grade (A216-WCB 등) 옵션 풀.
#   - Trim_Matl 단일 컬럼 (API 600 trim 조합): Gate/Globe 와 동일 옵션 풀.
#     Seat_Matl 폐지. data/field_values.json 의 Check_Valve_Group 참조.
#   - Size 시스템: Size1_From / Size1_To 한 짝 (Reducing 없음).
#   - Rating: std-aware (ASTM 7 + JIS 7 + KS 7 = 21개; 800# 포함) — Gate/Globe 와
#     동일 옵션 풀 + std 키 부여. ASTM 기준 표준은 ASME B16.34.
#   - End_Type 4종.
#
# 미고려 항목 (추후 도메인 합의 시 확장):
#   - Piston check 별도 컬럼 (현재 Lift 의 하위로 Remarks 우회)
#   - Body 형태 (Wafer / Lug / Full Body) 별도 컬럼 — 현재 Remarks 우회
#   - Non-slam closure (spring-assisted) 표시 컬럼
#   - Spring 재질 / 종류
#   - Actuator 종류 (자동 동작이라 무관)
#   - Item_Code 분리: Cast vs Forged (VC / VCF) 등 — 현재 VC 하나로 유지
#
# 다른 Valve 시트와의 공통 구조:
#   - 13 필드 (Gate/Globe 15개 - Bonnet_Stem/Operation 2개 = 13).
#   - Class_Name → Item_Code → Size1 → Body Matl → Trim → Rating →
#     End_Type → (Check 고유: Disc_Type) → Option_Code → Remarks 순서.

CHECK_VALVE_GROUP_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="Class_Name",
        meaning=(
            "이 행이 소속될 Class 의 이름. Pipe_Group.Class_Name 과 의미·검증"
            " 모두 동일."
        ),
        data_type="string",
        required=True,
        format_constraint=(
            "공백 trim. Class_Define.Class_Name 행 집합 기준 일치 검사."
        ),
        unique=None,
        relations=[
            "Class_Define.Class_Name 으로 FK",
        ],
        validation_location=(
            "Pipe_Group.Class_Name 과 동일 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class_Define 행 목록)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Item_Code",
        meaning=(
            "Check_Valve_Group 의 component 종류 식별자. 현재 'VC' (CHECK VALVE)"
            " 하나만 정의 — Disc 종류 차이 (Swing/Lift/Tilting/Dual/Ball) 는"
            " Disc_Type 컬럼으로 구분. Cast vs Forged 의 Item_Code 분리는 현재"
            " 미고려."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/item_code_db.json 의 Check_Valve_Group 행 (closed set, 현재"
            " 1개)."
        ),
        unique=None,
        relations=[
            "item_code_db.json Check_Valve_Group 의 code 값 중 하나 (FK)",
            "PMS description prefix 합성: VC → CHECK VALVE",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set 옵션 강제)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — item_code_db 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size1_From",
        meaning=(
            "NPS/DN size 범위의 하한. Gate_Valve_Group.Size1_From 과 동일 의미."
            " Valve 는 Reducing 없음 — 단일 size 짝 (Size1_From/Size1_To) 사용."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size1_From <= Size1_To 강제 (행 단위 검증, 별도 작업)."
        ),
        unique=None,
        relations=[
            "Class_Define.Size_From / Size_To 범위 안",
        ],
        validation_location=(
            "Pipe_Group.Size_From 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size1_To",
        meaning=(
            "NPS/DN size 범위의 상한. Size1_From 의 상한 짝."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size1_From <= Size1_To 강제."
        ),
        unique=None,
        relations=[
            "(Size1_From, Size1_To) 의 상한",
        ],
        validation_location=(
            "Pipe_Group.Size_To 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Category",
        meaning=(
            "Valve body 재질의 대분류 카테고리. Gate/Globe_Valve_Group 과 동일"
            " 7개 (CS/LTCS/AS/SS/DSS/SDSS/Ni-Alloy)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Check_Valve_Group.Matl_Category 옵션"
            " (closed set, 7개)."
        ),
        unique=None,
        relations=[
            "Matl_Std / Matl_Code 와 종속 체인 (Pipe_Group 패턴 동일)",
            "Trim_Matl / Seat_Matl 과는 독립",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Std",
        meaning=(
            "Valve body 재질 표준 발행 기관. 4개 (ASTM/JIS/KS/EN)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Check_Valve_Group.Matl_Std 옵션"
            " (closed set, 4개)."
        ),
        unique=None,
        relations=[
            "Matl_Code 의 std 키와 일치",
            "Rating 의 std 키와도 일치 — std-aware Rating 필터링",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Code",
        meaning=(
            "Valve body 의 구체 재질 규격 코드. **Cast grade** — Gate/Globe 와"
            " 동일 옵션 풀. ASTM (8): A216-WCB, A352-LCB/LCC, A351-CF8/CF8M,"
            " A217-WC1/WC6/WC9. JIS (2): SCS13A/SCS14A. KS/EN 항목은 추후."
        ),
        data_type="string (short code; e.g. A216-WCB / SCS13A)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Check_Valve_Group.Matl_Code 옵션"
            " (closed set, 10개). KS/EN 항목은 추후 추가."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK), Matl_Category (의미적 정합) 와 함께 필터링",
            "Trim_Matl / Seat_Matl 과는 독립",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중"
            " Matl_Std 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Trim_Matl",
        meaning=(
            "Valve trim 재질 조합 — seat/disc/stem 재질 세트를 하나의 값으로 표현."
            " API 600 trim number 표준 세트(전 번호)를 재질조합 문자열(short)로"
            " 저장. Gate/Globe 와 동일 옵션 풀. Seat_Matl 전용 필드는 폐지."
        ),
        data_type="string (재질조합 문자열)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Check_Valve_Group.Trim_Matl 옵션"
            " (closed set, API 600 trim 전 번호; 현재 28개)."
        ),
        unique=None,
        relations=[
            "seat/disc/stem 재질을 단일 값으로 통합 (Seat_Matl 필드 대체)",
            "PMS description 의 trim token 에 그대로 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Rating",
        meaning=(
            "Valve 의 압력 등급. std-aware 필드 — Gate/Globe 와 옵션 풀 동일,"
            " ASTM 기준 표준은 ASME **B16.34** (Valve)."
            "\n - ASTM: 150# / 300# / 600# / 800# / 900# / 1500# / 2500#."
            "\n - JIS: 5K / 10K / 16K / 20K / 30K / 40K / 63K."
            "\n - KS: 5K / 10K / 16K / 20K / 30K / 40K / 63K."
        ),
        data_type="string (short code; ASTM NNN# 형식 / JIS·KS prefix+NK 형식)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Check_Valve_Group.Rating 옵션"
            " (closed set, 21개 — 800# 포함)."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK) — std-aware 필터링의 1차 게이트",
            "Flange/Gate/Globe 의 Rating 과 옵션 풀 동일",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중 Matl_Std"
            " 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="End_Type",
        meaning=(
            "Valve 단부 (end connection) 형식. 4종:"
            " BW (Butt Weld — 용접), SW (Socket Weld), TH (Threaded — 나사),"
            " FLG (Flanged — 플랜지)."
            " Wafer / Lug body 는 별도 컬럼 미고려 (Remarks 우회) — 통상 End_Type"
            " 가 FLG 일 때 wafer/lug 가 가능."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Check_Valve_Group.End_Type 옵션"
            " (closed set, 6개)."
        ),
        unique=None,
        relations=[
            "End_Type 이 FLGD* 일 때 Rating 이 상대 flange 와 짝이 되어야 정합"
            " (facing 은 End_Type 토큰에 포함). (별도 검증 영역)",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Cover_Disc",
        meaning=(
            "Check Valve 의 cover 체결 방식 + disc(역류 차단부) 형식의 통합 분류."
            " **Check Valve 고유 컬럼** — Gate 의 Bonnet_Stem 과 동일 패턴 (cover 와"
            " disc 를 한 토큰으로 결합, 예: 'BC SWING'). 현실 조합 9개:"
            " BC SWING / BC LIFT / BC TILTING / PSC SWING / PSC TILTING /"
            " SC SWING / SC LIFT / DUAL PLATE / BALL."
            " cover BC=Bolted Cover · PSC=Pressure-Sealed Cover · SC=Screwed Cap;"
            " disc Swing(hinge 회전, API 6D) · Lift(수직, 소구경) · Tilting(대구경"
            " water hammer 방지). DUAL PLATE(wafer/lug, API 594) 와 BALL(소구경"
            " 점성)은 cover 개념이 약해 단독."
            " 빈 값 허용 — Procurement description 에 명시 안 하는 관행."
        ),
        data_type="string (short code; 빈 값 허용)",
        required=False,
        format_constraint=(
            "data/field_values.json 의 Check_Valve_Group.Cover_Disc 옵션"
            " (closed set, 9개 + 빈 값)."
        ),
        unique=None,
        relations=[
            "Size1 과 호환 관행: 2\"+ Swing, 소구경 Lift/Ball, 대구경 Tilting/"
            "Dual 이 통상 — 강제 검증 없음",
            "PMS description 에 합성 (빈 값이면 토큰 생략). Gate 의 Bonnet_Stem"
            " 자리에 대응 — Operation 은 없음(자동 밸브)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set, 빈 값 허용)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Option_Code",
        meaning=(
            "Item_Code 변종/옵션 식별자. Pipe_Group.Option_Code 와 의미·형식"
            " 동일 — 3자리 숫자 텍스트, '001' = 해당 Class · Check_Valve_Group"
            " 의 표준형."
        ),
        data_type="string (3자리 0-9 숫자 텍스트; e.g. '001')",
        required=True,
        format_constraint=(
            "정규식 ^\\d{3}$. data/field_values.json 의 Check_Valve_Group.Option_Code"
            " 옵션 (closed set). 현재 '001' 한 개만 등록."
        ),
        unique=(
            "(Class_Name, Option_Code) 가 Check_Valve_Group 시트 안에서 유일."
            " 다른 시트의 Option_Code 와는 독립."
        ),
        relations=[
            "(Class_Name, Option_Code) 가 Check_Valve_Group 행의 자연 키",
            "Pipe_Group.Option_Code 와 동일 패턴",
        ],
        validation_location=(
            "Pipe_Group.Option_Code 와 동일 패턴 — 검증 모두 현재 미구현."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Remarks",
        meaning=(
            "행 단위 비고/설명 자유 텍스트. Pipe_Group.Remarks 와 의미·동작 동일."
            " Piston check 변종 명시 (예: 'Piston Lift, spring-loaded'),"
            " Body 형태 (Wafer / Lug / Full Body — 별도 컬럼 미구현 단계 동안"
            " 우회), Non-slam closure 표시, Spring 재질 등을 자유 입력."
        ),
        data_type="string (자유 텍스트, 빈 값 허용)",
        required=False,
        format_constraint=(
            "형식 강제 없음 — data/field_values.json 의 _meta.free_input_fields"
            " 에 'Remarks' 명시 (모든 시트 공통)."
        ),
        unique=None,
        relations=[
            "PMS description 합성의 마지막 토큰 — Pipe_Group.Remarks 와 동일 패턴",
        ],
        validation_location=(
            "검증 없음 (자유 입력). required 아님."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 자유 텍스트 입력 (Entry widget)"
        ),
        unit=None,
    ),
]


# ── Ball_Valve_Group ───────────────────────────────────────────────────────────
#
# Ball Valve (회전 ball 로 차단하는 valve) — Valve 6종 중 네 번째 시트.
# Gate/Globe/Check 와 달리 Bonnet_Stem 컬럼 없음 (Ball valve 의 cover 구조는
# Entry_Type 으로 표현). 대신 Ball valve 고유의 두 컬럼이 추가:
#   - Bore (FB / RB): full bore 와 reduced bore 의 구분이 핵심.
#   - Entry_Type (Top / Side / End): body 분리 방식 (cover 형태).
#
# Gate/Globe/Check 와의 주요 차이:
#   - Bonnet_Stem 없음 — Ball valve 는 bonnet 대신 body cover (top / side / end
#     entry) 로 분리되며 그 구분이 Entry_Type 컬럼.
#   - Bore (FB / RB) 컬럼이 **required + 빈 값 불허** — Ball valve 는 FB/RB
#     구분이 도메인 핵심. Procurement Description 에 관행상 항상 포함.
#   - Entry_Type 은 required=False + 빈 값 허용 — 대구경 valve 는 명시, 소구경
#     표준 valve 는 생략하는 관행.
#   - Body Matl_Code 풀이 **cast + forged 혼합** — Gate/Globe 의 cast 전용 풀과
#     달리 Ball valve 는 소구경 (≤ 4\") forged body 가 흔함 (A105, A350-LF2,
#     A182-F316 포함).
#   - Seat_Matl 풀이 **soft seat 위주** (PTFE / RPTFE / Devlon / Nylon) +
#     metal seat (F316 / Stellite-6) 일부. Ball valve 표준은 "floating ball +
#     soft seat" 가 많음.
#   - Trim_Matl 5종 (F316/F304/13Cr/Inconel-625/Monel-400) — Gate/Globe 의 7종
#     보다 좁은 풀 (Stellite-6 / Hastelloy 제외; Ball stem 은 hardfacing 덜
#     필요).
#
# Gate/Globe/Check 와 동일한 부분:
#   - Size 시스템: Size1_From / Size1_To 한 짝 (Reducing 없음).
#   - Rating: std-aware (ASTM 6 + JIS 7 + KS 7 = 20개) — 동일 옵션 풀 + std 키.
#     ASTM 기준 표준은 ASME B16.34.
#   - End_Type 4종 (BW/SW/TH/FLG).
#   - Operation 5종 (Manual/Lever/Wrench/Gear/Chain) — 소구경 Lever, 대구경
#     Gear 가 흔함.
#
# 미고려 항목 (추후 도메인 합의 시 확장):
#   - Ball 종류 (Floating Ball / Trunnion Mounted Ball) — 대구경/고압은 Trunnion
#     이 표준, 현재 Remarks 우회
#   - Sealing 종류 (DBB / DIB-1 / DIB-2 등 API 6D 분류)
#   - Anti-static / Fire-safe / Anti-blowout stem 설계 옵션
#   - Stem extension (long stem for buried service)
#   - Actuator 종류 (Motor / Pneumatic / Hydraulic) — 별도 actuator 시트
#   - Trim_Matl / Seat_Matl 의 std-aware 필터링
#   - Item_Code 분리: Cast vs Forged (VL / VLF) 등 — 현재 VL 하나로 유지
#
# 다른 Valve 시트와의 공통 구조:
#   - 16 필드 (Gate/Globe 와 동일 길이; Bonnet_Stem 자리에 Bore + Entry_Type
#     두 컬럼이 차지).
#   - Class_Name → Item_Code → Size1 → Body Matl → Trim/Seat → Rating →
#     End_Type → (Ball 고유: Bore → Entry_Type) → Operation → Option_Code →
#     Remarks 순서.

BALL_VALVE_GROUP_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="Class_Name",
        meaning=(
            "이 행이 소속될 Class 의 이름. Pipe_Group.Class_Name 과 의미·검증"
            " 모두 동일."
        ),
        data_type="string",
        required=True,
        format_constraint=(
            "공백 trim. Class_Define.Class_Name 행 집합 기준 일치 검사."
        ),
        unique=None,
        relations=[
            "Class_Define.Class_Name 으로 FK",
        ],
        validation_location=(
            "Pipe_Group.Class_Name 과 동일 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class_Define 행 목록)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Item_Code",
        meaning=(
            "Ball_Valve_Group 의 component 종류 식별자. 현재 'VL' (BALL VALVE)"
            " 하나만 정의 — Bore/Entry_Type/Trim/Seat 의 조합으로 ball valve"
            " 변종 표현. Cast vs Forged 의 Item_Code 분리는 현재 미고려."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/item_code_db.json 의 Ball_Valve_Group 행 (closed set, 현재"
            " 1개)."
        ),
        unique=None,
        relations=[
            "item_code_db.json Ball_Valve_Group 의 code 값 중 하나 (FK)",
            "PMS description prefix 합성: VL → BALL VALVE",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set 옵션 강제)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — item_code_db 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size1_From",
        meaning=(
            "NPS/DN size 범위의 하한. Gate_Valve_Group.Size1_From 과 동일 의미."
            " Valve 는 Reducing 없음 — 단일 size 짝 (Size1_From/Size1_To) 사용."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size1_From <= Size1_To 강제 (행 단위 검증, 별도 작업)."
        ),
        unique=None,
        relations=[
            "Class_Define.Size_From / Size_To 범위 안",
        ],
        validation_location=(
            "Pipe_Group.Size_From 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size1_To",
        meaning=(
            "NPS/DN size 범위의 상한. Size1_From 의 상한 짝."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size1_From <= Size1_To 강제."
        ),
        unique=None,
        relations=[
            "(Size1_From, Size1_To) 의 상한",
        ],
        validation_location=(
            "Pipe_Group.Size_To 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Category",
        meaning=(
            "Valve body 재질의 대분류 카테고리. Gate/Globe_Valve_Group 과 동일"
            " 7개 (CS/LTCS/AS/SS/DSS/SDSS/Ni-Alloy)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Ball_Valve_Group.Matl_Category 옵션"
            " (closed set, 7개)."
        ),
        unique=None,
        relations=[
            "Matl_Std / Matl_Code 와 종속 체인 (Pipe_Group 패턴 동일)",
            "Trim_Matl / Seat_Matl 과는 독립",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Std",
        meaning=(
            "Valve body 재질 표준 발행 기관. 4개 (ASTM/JIS/KS/EN)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Ball_Valve_Group.Matl_Std 옵션"
            " (closed set, 4개)."
        ),
        unique=None,
        relations=[
            "Matl_Code 의 std 키와 일치",
            "Rating 의 std 키와도 일치 — std-aware Rating 필터링",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Code",
        meaning=(
            "Valve body 의 구체 재질 규격 코드. **Cast + Forged 혼합 풀** —"
            " Ball valve 는 소구경 (≤ 4\") forged body 가 흔하므로 Gate/Globe 의"
            " cast 전용 풀과 다름. ASTM (8): A216-WCB (CS Cast), A352-LCB/LCC"
            " (LTCS Cast), A351-CF8/CF8M (SS Cast), A105 (CS Forged), A350-LF2"
            " (LTCS Forged), A182-F316 (SS Forged). JIS (2): SCS13A/SCS14A"
            " (SS Cast). KS/EN 항목은 추후."
        ),
        data_type="string (short code; e.g. A216-WCB / A105 / SCS13A)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Ball_Valve_Group.Matl_Code 옵션"
            " (closed set, 10개). KS/EN 항목은 추후 추가."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK), Matl_Category (의미적 정합) 와 함께 필터링",
            "Trim_Matl / Seat_Matl 과는 독립",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중"
            " Matl_Std 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Trim_Matl",
        meaning=(
            "Valve trim (stem / ball / 내부 부품) 재질. 5종: F316, F304, 13Cr,"
            " Inconel-625, Monel-400 — Gate/Globe 의 7종 보다 좁은 풀"
            " (Stellite-6 / Hastelloy-C276 미포함). Ball stem 은 ball 의 회전"
            " 동작 특성상 sliding wear 가 적어 hardfacing 덜 필요."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Ball_Valve_Group.Trim_Matl 옵션"
            " (closed set, 5개)."
        ),
        unique=None,
        relations=[
            "Seat_Matl 와 호환 관행: ball (trim) vs seat 재질 조합으로 가격/내구"
            " 결정 — 강제 검증 없음",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Seat_Matl",
        meaning=(
            "Valve seat (ball 과 접촉하는 면) 재질. **Soft seat 위주** 6종:"
            " PTFE, RPTFE (Reinforced PTFE), Devlon, Nylon, F316, Stellite-6."
            " Ball valve 표준은 'floating ball + soft seat' 가 많아 polymer"
            " seat (PTFE 계열) 이 표준; metal seat (F316 / Stellite-6) 는 고온"
            " 또는 hard service 용 — Gate/Globe 의 metal-only seat 와 차이."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Ball_Valve_Group.Seat_Matl 옵션"
            " (closed set, 6개)."
        ),
        unique=None,
        relations=[
            "Trim_Matl 와 호환 관행 (위 Trim_Matl.relations 참조)",
            "Rating 과 호환 관행: 고온/고압 → metal seat 권장 — 강제 검증 없음",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Rating",
        meaning=(
            "Valve 의 압력 등급. std-aware 필드 — Flange/Gasket/Gate/Globe/Check"
            " 와 옵션 풀 동일 (20개), ASTM 기준 표준은 ASME **B16.34** (Valve)."
            "\n - ASTM: 150# / 300# / 600# / 900# / 1500# / 2500#."
            "\n - JIS: 5K / 10K / 16K / 20K / 30K / 40K / 63K."
            "\n - KS: 5K / 10K / 16K / 20K / 30K / 40K / 63K."
        ),
        data_type="string (short code; ASTM NNN# 형식 / JIS·KS prefix+NK 형식)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Ball_Valve_Group.Rating 옵션"
            " (closed set, 20개)."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK) — std-aware 필터링의 1차 게이트",
            "Flange/Gate/Globe/Check 의 Rating 과 옵션 풀 동일",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중 Matl_Std"
            " 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="End_Type",
        meaning=(
            "Valve 단부 (end connection) 형식. 4종:"
            " BW (Butt Weld), SW (Socket Weld), TH (Threaded), FLG (Flanged)."
            " Mechanical joint / Grooved 등은 현재 미고려."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Ball_Valve_Group.End_Type 옵션"
            " (closed set, 6개)."
        ),
        unique=None,
        relations=[
            "End_Type 이 FLGD* 일 때 Rating 이 상대 flange 와 짝이 되어야 정합"
            " (facing 은 End_Type 토큰에 포함). (별도 검증 영역)",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Bore",
        meaning=(
            "Ball valve 의 bore 형식. **Ball Valve 고유 컬럼** — 2종:"
            " FB (Full Bore — ball 내경이 line 내경과 동일, pigging 가능),"
            " RB (Reduced Bore — ball 내경이 line 보다 작음, 경제적 + Cv 감소)."
            " 빈 값 불허 — Ball valve 는 FB/RB 구분이 도메인 핵심으로 항상 명시."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Ball_Valve_Group.Bore 옵션"
            " (closed set, 2개)."
        ),
        unique=None,
        relations=[
            "Size1 과 호환 관행: 대구경 + pigging 요구 → FB, 일반 차단용 → RB"
            " 가 흔함 — 강제 검증 없음",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Entry_Type",
        meaning=(
            "Ball valve body 분리 방식 (cover 형식). **Ball Valve 고유 컬럼** —"
            " 3종 + 빈 값:"
            " Top (Top Entry — body 상단 cover, in-line maintenance 가능),"
            " Side (Side Entry — body 가 두 조각, Split Body; 가장 흔함),"
            " End (End Entry — body 가 두 조각, end 쪽 분리)."
            " 빈 값 허용 — 대구경 valve 는 명시, 소구경 표준 valve 는 생략하는"
            " 관행."
        ),
        data_type="string (short code; 빈 값 허용)",
        required=False,
        format_constraint=(
            "data/field_values.json 의 Ball_Valve_Group.Entry_Type 옵션"
            " (closed set, 3개 + 빈 값)."
        ),
        unique=None,
        relations=[
            "Size1 과 호환 관행: 대구경 + 고압 → Top Entry (in-line maintenance"
            " 필요) 가 흔함 — 강제 검증 없음",
            "PMS description 에 합성 (빈 값이면 토큰 생략)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set, 빈 값 허용)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Operation",
        meaning=(
            "Valve 조작 방식. 5종:"
            " Manual (Handwheel — 대구경 ball 에 흔함),"
            " Lever (소구경 ball valve 의 표준),"
            " Wrench (Wrench Operated), Gear (Gear Operated — 대구경),"
            " Chain (Chain Operated — 높은 위치)."
            " Motor / Pneumatic / Hydraulic 등 actuator 는 현재 미고려 (별도"
            " actuator 시트로 분리 검토)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Ball_Valve_Group.Operation 옵션"
            " (closed set, 5개)."
        ),
        unique=None,
        relations=[
            "Size1 과 호환 관행: ≤ 2\" 는 Lever, 4\"~6\" 는 Gear, 대구경은 actuator"
            " 가 흔함 — 강제 검증 없음",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Option_Code",
        meaning=(
            "Item_Code 변종/옵션 식별자. Pipe_Group.Option_Code 와 의미·형식"
            " 동일 — 3자리 숫자 텍스트, '001' = 해당 Class · Ball_Valve_Group"
            " 의 표준형."
        ),
        data_type="string (3자리 0-9 숫자 텍스트; e.g. '001')",
        required=True,
        format_constraint=(
            "정규식 ^\\d{3}$. data/field_values.json 의 Ball_Valve_Group.Option_Code"
            " 옵션 (closed set). 현재 '001' 한 개만 등록."
        ),
        unique=(
            "(Class_Name, Option_Code) 가 Ball_Valve_Group 시트 안에서 유일."
            " 다른 시트의 Option_Code 와는 독립."
        ),
        relations=[
            "(Class_Name, Option_Code) 가 Ball_Valve_Group 행의 자연 키",
            "Pipe_Group.Option_Code 와 동일 패턴",
        ],
        validation_location=(
            "Pipe_Group.Option_Code 와 동일 패턴 — 검증 모두 현재 미구현."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Remarks",
        meaning=(
            "행 단위 비고/설명 자유 텍스트. Pipe_Group.Remarks 와 의미·동작 동일."
            " Ball 종류 (Floating / Trunnion Mounted), Sealing 분류 (DBB /"
            " DIB-1 / DIB-2 등 API 6D), Anti-static / Fire-safe 옵션, Stem"
            " extension 등을 자유 입력."
        ),
        data_type="string (자유 텍스트, 빈 값 허용)",
        required=False,
        format_constraint=(
            "형식 강제 없음 — data/field_values.json 의 _meta.free_input_fields"
            " 에 'Remarks' 명시 (모든 시트 공통)."
        ),
        unique=None,
        relations=[
            "PMS description 합성의 마지막 토큰 — Pipe_Group.Remarks 와 동일 패턴",
        ],
        validation_location=(
            "검증 없음 (자유 입력). required 아님."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 자유 텍스트 입력 (Entry widget)"
        ),
        unit=None,
    ),
]


# ── Butterfly_Valve_Group ──────────────────────────────────────────────────────
#
# Butterfly Valve (회전 disc 로 차단·조절하는 valve) — Valve 6종 중 다섯 번째.
# 다른 valve 와 구조적으로 가장 다른 시트: 저압·경량·short face-to-face 특성이
# 풀과 헤더 모두에 반영됨.
#
# 다른 Valve 시트와의 주요 차이:
#   - **Trim_Matl 대신 Disc_Matl** — Butterfly 의 핵심 부품은 disc 이며 stem
#     trim 보다 disc 재질이 중요 (Gate/Globe/Check/Ball 의 Trim_Matl 자리).
#   - **Matl_Category 6종** — AS / SDSS 제외, **CI (Cast Iron) 추가**. Butterfly
#     는 저압 일반 (≤ 600#) 이라 cast iron body 가 흔함.
#   - **Matl_Code 풀에 A126-B / A395 포함** — 각각 gray iron / ductile iron"
#     cast (저압 cast iron grade).
#   - **Seat_Matl 풀이 soft seat 중심** (EPDM / NBR / PTFE / RPTFE) + metal
#     일부 (F316 / Stellite-6). EPDM/NBR 은 Butterfly 만의 옵션 (다른 valve
#     에 없음).
#   - **Rating 11종만** (다른 valve 의 20종 보다 좁음) — ASTM: 150# / 300# /
#     600# 만 (900# 이상 없음). JIS/KS: 5K ~ 20K 만 (30K 이상 없음).
#   - **End_Type 컬럼 없음** — Butterfly 는 body 형태(Body_Type) 자체가 연결
#     방식을 결정하므로 일반 valve 의 End_Type(BW/SW/TH/FLGD) 체계를 두지 않는다.
#   - **Bonnet_Stem / Bore 없음** — Butterfly 는 bonnet 개념 약하고 (top cover
#     로 stem 만), bore 는 항상 line size 와 거의 동일.
#   - **Disc_Type 컬럼 신설 (Butterfly 고유)** — disc geometry 가 도메인 분류의
#     핵심. 3종 + 빈 값:
#       · Concentric (Zero Offset / Resilient Seated): stem 이 disc 중심,
#         소프트 seat 와 짝. 저압 일반.
#       · DoubleOffset (High Performance): stem 이 disc 면에서 오프셋, metal/
#         PTFE seat 가능. 중압.
#       · TripleOffset (TOV — Triple Offset Valve): 추가 conical seat offset,
#         metal seat tight closure. 고압·고온, ASME B16.34 적용.
#       · (빈 값): Procurement Description 에 명시 안 하는 케이스.
#   - **Body_Type 컬럼 (Butterfly 고유) = 연결 방식 겸함** — body 형태 (API 609
#     표준). End_Type 을 대체 (Wafer/Lug/Double-Flanged 가 곧 end connection).
#     4종, 빈 값 불허 (required + Ball Bore / Plug Plug_Type 패턴):
#       · Wafer: 두 flange 사이에 끼움 — 가장 컴팩트/저렴, dead-end service
#         불가 (양쪽 flange 모두 있어야 sealing).
#       · Lug: threaded lugs 로 flange 별도 bolt — dead-end service 가능,
#         downstream 분리 가능.
#       · Double-Flanged: body 에 flange 통합 — 고압·고온 안정성, NPS 3~36.
#       · Butt-Weld: 용접 단부 — API 609 2021 추가, 현장에선 드묾.
#
# 다른 Valve 시트와 동일한 부분:
#   - Size 시스템: Size1_From / Size1_To 한 짝 (Reducing 없음).
#   - Rating std-aware (std 키 부여) — 옵션 풀은 다른 valve 보다 좁지만 std
#     필드 구조는 동일.
#   - Operation 5종 (Manual/Lever/Wrench/Gear/Chain) — 소구경 Lever, 대구경
#     Gear 가 흔함.
#
# 미고려 항목 (추후 도메인 합의 시 확장):
#   - U-Section body — 표준 외 변종, 현재 Body_Type 옵션에 미포함.
#   - Seat alignment (loose / locked) — Triple Offset 의 세부 옵션.
#   - Actuator 종류 (Motor / Pneumatic / Hydraulic) — 별도 actuator 시트.
#   - Stem extension / Bare stem 옵션.
#   - Item_Code 분리: Resilient Seated vs High Performance (VU / VUH) 등 —
#     현재 VU 하나로 유지, 구분은 Disc_Type 컬럼.
#
# 다른 Valve 시트와의 공통 구조:
#   - 16 필드 (Gate/Globe/Ball 16개; Butterfly 도 Body_Type 추가로 16개).
#   - Class_Name → Item_Code → Size1 → Body Matl → Disc_Matl/Seat_Matl →
#     Rating → End_Type → (Butterfly 고유: Body_Type) → Operation →
#     (Butterfly 고유: Disc_Type) → Option_Code → Remarks 순서.

BUTTERFLY_VALVE_GROUP_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="Class_Name",
        meaning=(
            "이 행이 소속될 Class 의 이름. Pipe_Group.Class_Name 과 의미·검증"
            " 모두 동일."
        ),
        data_type="string",
        required=True,
        format_constraint=(
            "공백 trim. Class_Define.Class_Name 행 집합 기준 일치 검사."
        ),
        unique=None,
        relations=[
            "Class_Define.Class_Name 으로 FK",
        ],
        validation_location=(
            "Pipe_Group.Class_Name 과 동일 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class_Define 행 목록)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Item_Code",
        meaning=(
            "Butterfly_Valve_Group 의 component 종류 식별자. 현재 'VU'"
            " (BUTTERFLY VALVE) 하나만 정의 — Disc geometry 차이 (Concentric/"
            "DoubleOffset/TripleOffset) 는 Disc_Type 컬럼으로 구분."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/item_code_db.json 의 Butterfly_Valve_Group 행 (closed set,"
            " 현재 1개)."
        ),
        unique=None,
        relations=[
            "item_code_db.json Butterfly_Valve_Group 의 code 값 중 하나 (FK)",
            "PMS description prefix 합성: VU → BUTTERFLY VALVE",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set 옵션 강제)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — item_code_db 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size1_From",
        meaning=(
            "NPS/DN size 범위의 하한. Gate_Valve_Group.Size1_From 과 동일 의미."
            " Valve 는 Reducing 없음 — 단일 size 짝 (Size1_From/Size1_To) 사용."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size1_From <= Size1_To 강제 (행 단위 검증, 별도 작업)."
        ),
        unique=None,
        relations=[
            "Class_Define.Size_From / Size_To 범위 안",
        ],
        validation_location=(
            "Pipe_Group.Size_From 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size1_To",
        meaning=(
            "NPS/DN size 범위의 상한. Size1_From 의 상한 짝."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size1_From <= Size1_To 강제."
        ),
        unique=None,
        relations=[
            "(Size1_From, Size1_To) 의 상한",
        ],
        validation_location=(
            "Pipe_Group.Size_To 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Category",
        meaning=(
            "Valve body 재질의 대분류 카테고리. **6종** (Butterfly 고유 풀) —"
            " CS / LTCS / SS / DSS / Ni-Alloy / **CI (Cast Iron)**. 다른 valve"
            " 의 7종에서 AS / SDSS 제외 + CI 추가. Butterfly 는 저압 일반 (≤"
            " 600#) 이라 cast iron body 가 흔함."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Butterfly_Valve_Group.Matl_Category 옵션"
            " (closed set, 6개)."
        ),
        unique=None,
        relations=[
            "Matl_Std / Matl_Code 와 종속 체인 (Pipe_Group 패턴 동일)",
            "Disc_Matl / Seat_Matl 과는 독립",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Std",
        meaning=(
            "Valve body 재질 표준 발행 기관. 4개 (ASTM/JIS/KS/EN)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Butterfly_Valve_Group.Matl_Std 옵션"
            " (closed set, 4개)."
        ),
        unique=None,
        relations=[
            "Matl_Code 의 std 키와 일치",
            "Rating 의 std 키와도 일치 — std-aware Rating 필터링",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Code",
        meaning=(
            "Valve body 의 구체 재질 규격 코드. **Cast iron grade 포함** —"
            " Butterfly 고유. ASTM (6): A216-WCB (CS Cast), A352-LCB (LTCS"
            " Cast), A351-CF8/CF8M (SS Cast), **A126-B (Gray Iron Cl.B), A395"
            " (Ductile Iron)**. JIS (2): SCS13A/SCS14A (SS Cast). KS/EN 항목은"
            " 추후."
        ),
        data_type="string (short code; e.g. A216-WCB / A126-B / A395)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Butterfly_Valve_Group.Matl_Code 옵션"
            " (closed set, 8개). KS/EN 항목은 추후 추가."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK), Matl_Category (의미적 정합) 와 함께 필터링",
            "Disc_Matl / Seat_Matl 과는 독립",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중"
            " Matl_Std 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Disc_Matl",
        meaning=(
            "Butterfly Valve disc 재질. **Butterfly 고유 컬럼** — 다른 valve 의"
            " Trim_Matl 자리에 대응 (Butterfly 의 핵심 부품은 disc). 5종:"
            " F316, F304, 13Cr, Inconel-625, Bronze (Aluminum Bronze). Body 와"
            " 다른 재질 선택 — 저압 cast iron body + SS316 disc 가 흔함."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Butterfly_Valve_Group.Disc_Matl 옵션"
            " (closed set, 5개)."
        ),
        unique=None,
        relations=[
            "Seat_Matl 와 호환 관행: disc 와 seat 의 재질 짝이 sealing 성능 결정",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Seat_Matl",
        meaning=(
            "Valve seat (disc 와 접촉하는 면) 재질. **Soft seat 중심** 6종:"
            " EPDM (Rubber), NBR, PTFE, RPTFE (Reinforced PTFE), F316,"
            " Stellite-6. EPDM/NBR 은 Butterfly 만의 옵션 — Concentric"
            " (Resilient Seated) 형식에 흔함. Metal seat (F316 / Stellite-6)"
            " 는 Triple Offset 의 고온·고압 용."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Butterfly_Valve_Group.Seat_Matl 옵션"
            " (closed set, 6개)."
        ),
        unique=None,
        relations=[
            "Disc_Matl 와 호환 관행 (위 Disc_Matl.relations 참조)",
            "Disc_Type 과 호환 관행: Concentric → soft seat, TripleOffset →"
            " metal seat 가 통상 — 강제 검증 없음",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Rating",
        meaning=(
            "Valve 의 압력 등급. std-aware 필드 — 다른 valve 의 20종 보다 좁은"
            " **11종** 풀 (Butterfly 는 저압 일반):"
            "\n - ASTM: 150# / 300# / 600# (900# 이상 없음)."
            "\n - JIS: 5K / 10K / 16K / 20K (30K 이상 없음)."
            "\n - KS: 5K / 10K / 16K / 20K (30K 이상 없음)."
            "\n ASTM 기준 표준은 ASME B16.34 (Triple Offset 이상의 metal seat"
            " 형식)."
        ),
        data_type="string (short code; ASTM NNN# 형식 / JIS·KS prefix+NK 형식)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Butterfly_Valve_Group.Rating 옵션"
            " (closed set, 11개)."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK) — std-aware 필터링의 1차 게이트",
            "다른 valve Rating 풀의 부분집합 (저압 영역만)",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중 Matl_Std"
            " 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Body_Type",
        meaning=(
            "Butterfly Valve 의 body 형태 = 연결 방식 (API 609 표준 4종)."
            " **Butterfly 고유 컬럼** — 일반 valve 의 End_Type(BW/SW/TH/FLGD)"
            " 체계 대신 body 형태 자체가 연결 방식을 결정하므로 End_Type 컬럼은"
            " 두지 않는다 (Wafer/Lug/Double-Flanged 가 곧 end connection):"
            " Wafer (두 flange 사이에 끼움 — 가장 컴팩트/저렴, dead-end service"
            " 불가),"
            " Lug (threaded lugs 로 flange 별도 bolt — dead-end service 가능),"
            " Double-Flanged (body 에 flange 통합 — 고압·고온 안정성),"
            " Butt-Weld (용접 단부 — API 609 2021 추가, 드묾)."
            " 빈 값 불허 — Butterfly valve 도메인 핵심 분류로 항상 명시."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Butterfly_Valve_Group.Body_Type 옵션"
            " (closed set, 4개)."
        ),
        unique=None,
        relations=[
            "연결 방식을 겸함 — Wafer/Lug/Double-Flanged 면 Rating + Facing 이"
            " 상대 flange 와 짝이 되어야 정합 (별도 검증 영역)",
            "Body_Type=Wafer 일 때 dead-end service 금지 — 도메인 관행, 강제"
            " 검증 없음",
            "Body_Type=Double-Flanged 일 때 Rating 고압 (300# 이상) 흔함 —"
            " 강제 검증 없음",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Operation",
        meaning=(
            "Valve 조작 방식. 5종:"
            " Manual (Handwheel), Lever (소구경 표준),"
            " Wrench (Wrench Operated), Gear (Gear Operated — 대구경),"
            " Chain (Chain Operated — 높은 위치)."
            " Motor / Pneumatic / Hydraulic 등 actuator 는 현재 미고려 (별도"
            " actuator 시트로 분리 검토). Butterfly 는 자동 actuator 적용이"
            " 흔하지만 현재 PMS 단계에선 manual 조작만 등록."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Butterfly_Valve_Group.Operation 옵션"
            " (closed set, 5개)."
        ),
        unique=None,
        relations=[
            "Size1 과 호환 관행: ≤ 4\" 는 Lever, 6\"~ 는 Gear 가 흔함 — 강제 검증"
            " 없음",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Disc_Type",
        meaning=(
            "Butterfly Valve disc geometry. **Butterfly 고유 컬럼** — Gate 의"
            " Wedge_Type, Globe 의 Disc_Type, Ball 의 Bore 자리에 대응. 3종:"
            " Concentric (Zero Offset, Resilient Seated — 저압 표준),"
            " DoubleOffset (High Performance — 중압, PTFE/metal seat),"
            " TripleOffset (TOV, conical seat — 고압·고온, metal seat,"
            " ASME B16.34)."
            " 빈 값 허용 — Procurement description 에 명시 안 하는 케이스."
        ),
        data_type="string (short code; 빈 값 허용)",
        required=False,
        format_constraint=(
            "data/field_values.json 의 Butterfly_Valve_Group.Disc_Type 옵션"
            " (closed set, 3개 + 빈 값)."
        ),
        unique=None,
        relations=[
            "Seat_Matl 과 호환 관행: Concentric → EPDM/NBR/PTFE, TripleOffset"
            " → metal seat (F316 / Stellite-6) 가 통상 — 강제 검증 없음",
            "Rating 과 호환 관행: TripleOffset 은 600#+ 고압 영역이 흔함",
            "PMS description 에 합성 (빈 값이면 토큰 생략)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set, 빈 값 허용)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Option_Code",
        meaning=(
            "Item_Code 변종/옵션 식별자. Pipe_Group.Option_Code 와 의미·형식"
            " 동일 — 3자리 숫자 텍스트, '001' = 해당 Class · Butterfly_Valve_"
            "Group 의 표준형."
        ),
        data_type="string (3자리 0-9 숫자 텍스트; e.g. '001')",
        required=True,
        format_constraint=(
            "정규식 ^\\d{3}$. data/field_values.json 의 Butterfly_Valve_Group."
            "Option_Code 옵션 (closed set). 현재 '001' 한 개만 등록."
        ),
        unique=(
            "(Class_Name, Option_Code) 가 Butterfly_Valve_Group 시트 안에서"
            " 유일. 다른 시트의 Option_Code 와는 독립."
        ),
        relations=[
            "(Class_Name, Option_Code) 가 Butterfly_Valve_Group 행의 자연 키",
            "Pipe_Group.Option_Code 와 동일 패턴",
        ],
        validation_location=(
            "Pipe_Group.Option_Code 와 동일 패턴 — 검증 모두 현재 미구현."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Remarks",
        meaning=(
            "행 단위 비고/설명 자유 텍스트. Pipe_Group.Remarks 와 의미·동작 동일."
            " Body type (Wafer / Lug / Double-Flanged 등 — 별도 컬럼 미구현"
            " 단계 동안 우회), Actuator 정보 (Motor / Pneumatic 등), Seat"
            " alignment (loose / locked), Stem extension 등을 자유 입력."
        ),
        data_type="string (자유 텍스트, 빈 값 허용)",
        required=False,
        format_constraint=(
            "형식 강제 없음 — data/field_values.json 의 _meta.free_input_fields"
            " 에 'Remarks' 명시 (모든 시트 공통)."
        ),
        unique=None,
        relations=[
            "PMS description 합성의 마지막 토큰 — Pipe_Group.Remarks 와 동일 패턴",
        ],
        validation_location=(
            "검증 없음 (자유 입력). required 아님."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 자유 텍스트 입력 (Entry widget)"
        ),
        unit=None,
    ),
]


# ── Plug_Valve_Group ───────────────────────────────────────────────────────────
#
# Plug Valve (회전 plug 로 차단하는 valve) — Valve 6종 중 여섯 번째, **Component
# 계층 12 시트의 마지막**.
# API 599 표준의 plug valve 기준 — 윤활 여부로 두 종류로 나뉨.
#
# 다른 Valve 시트와의 주요 차이:
#   - **Trim_Matl 대신 Plug_Matl** — Plug 자체 (회전부) 의 재질. Butterfly 의"
#     Disc_Matl 과 유사 패턴.
#   - **Plug_Type 컬럼 (Plug valve 고유) — required + 빈 값 불허**:
#       · Lubricated: 윤활제 주입형 — sealing 은 윤활제 film 이 담당. 고압·고온"
#         용 (고온 윤활제 사용).
#       · Non-Lubricated: PTFE sleeve 등 비금속 sleeve 가 plug 를 감싸 soft"
#         seat 역할 — 가장 흔함, API 599 표준 형식. (Sleeved 라는 별칭은 본"
#         시트에서 Non-Lubricated 와 동의어로 통합.)
#     Eccentric / Expanding plug valve 는 현재 미고려 (특수 변종 — slurry / DBB"
#     용; 추후 도메인 합의 시 옵션 확장).
#   - **Seat_Matl 풀이 sleeve material 위주** — PTFE / Viton / F316 / Stellite-6"
#     4종. Non-Lubricated 의 경우 PTFE sleeve 가 표준 (도메인 정의: sleeve =\
#     soft seat). Lubricated 의 경우 metal seat 가 흔함.
#   - **Matl_Category 6종** — SDSS 제외 (다른 valve 의 7종 중). Plug valve 는"
#     SDSS 용도가 드묾.
#
# 다른 Valve 시트와 동일한 부분:
#   - Size 시스템: Size1_From / Size1_To 한 짝 (Reducing 없음).
#   - Rating: std-aware (ASTM 6 + JIS 7 + KS 7 = 20개) — Gate/Globe/Check/Ball"
#     과 동일 옵션 풀 + std 키 부여. ASTM 기준 표준은 ASME B16.34.
#   - End_Type 4종 (BW/SW/TH/FLG).
#   - Operation 5종 (Manual/Lever/Wrench/Gear/Chain).
#   - Bonnet_Stem 없음 — Plug valve 는 bonnet 대신 top cover (stem 만 외부로"
#     노출).
#
# 미고려 항목 (추후 도메인 합의 시 확장):
#   - Eccentric Plug Valve (slurry / wear 용 오프셋 plug)
#   - Expanding Plug Valve (DBB 용 plug 확장 메커니즘)
#   - Multi-port plug valve (3-way, 4-way)
#   - Sleeve 재질 std-aware 필터링
#   - Actuator 종류 (Motor / Pneumatic / Hydraulic) — 별도 actuator 시트
#   - Item_Code 분리: Lubricated vs Non-Lubricated (VP / VPN) — 현재 VP 하나로"
#     유지, 구분은 Plug_Type 컬럼.
#
# 다른 Valve 시트와의 공통 구조:
#   - 15 필드 (Gate/Globe/Ball 16개 - Bonnet_Stem 1개 = 15; Butterfly 와 동일"
#     길이).
#   - Class_Name → Item_Code → Size1 → Body Matl → Plug_Matl/Seat_Matl →"
#     Rating → End_Type → Operation → (Plug 고유: Plug_Type) → Option_Code →"
#     Remarks 순서.

PLUG_VALVE_GROUP_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="Class_Name",
        meaning=(
            "이 행이 소속될 Class 의 이름. Pipe_Group.Class_Name 과 의미·검증"
            " 모두 동일."
        ),
        data_type="string",
        required=True,
        format_constraint=(
            "공백 trim. Class_Define.Class_Name 행 집합 기준 일치 검사."
        ),
        unique=None,
        relations=[
            "Class_Define.Class_Name 으로 FK",
        ],
        validation_location=(
            "Pipe_Group.Class_Name 과 동일 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class_Define 행 목록)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Item_Code",
        meaning=(
            "Plug_Valve_Group 의 component 종류 식별자. 현재 'VP' (PLUG VALVE)"
            " 하나만 정의 — Lubricated/Non-Lubricated 구분은 Plug_Type 컬럼."
            " Eccentric/Expanding 같은 특수 변종은 현재 미고려."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/item_code_db.json 의 Plug_Valve_Group 행 (closed set, 현재"
            " 1개)."
        ),
        unique=None,
        relations=[
            "item_code_db.json Plug_Valve_Group 의 code 값 중 하나 (FK)",
            "PMS description prefix 합성: VP → PLUG VALVE",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set 옵션 강제)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — item_code_db 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size1_From",
        meaning=(
            "NPS/DN size 범위의 하한. Gate_Valve_Group.Size1_From 과 동일 의미."
            " Valve 는 Reducing 없음 — 단일 size 짝 (Size1_From/Size1_To) 사용."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size1_From <= Size1_To 강제 (행 단위 검증, 별도 작업)."
        ),
        unique=None,
        relations=[
            "Class_Define.Size_From / Size_To 범위 안",
        ],
        validation_location=(
            "Pipe_Group.Size_From 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size1_To",
        meaning=(
            "NPS/DN size 범위의 상한. Size1_From 의 상한 짝."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size1_From <= Size1_To 강제."
        ),
        unique=None,
        relations=[
            "(Size1_From, Size1_To) 의 상한",
        ],
        validation_location=(
            "Pipe_Group.Size_To 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Category",
        meaning=(
            "Valve body 재질의 대분류 카테고리. **6종** (SDSS 제외) —"
            " CS / LTCS / AS / SS / DSS / Ni-Alloy. Plug valve 는 SDSS 용도가"
            " 드묾."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Plug_Valve_Group.Matl_Category 옵션"
            " (closed set, 6개)."
        ),
        unique=None,
        relations=[
            "Matl_Std / Matl_Code 와 종속 체인 (Pipe_Group 패턴 동일)",
            "Plug_Matl / Seat_Matl 과는 독립",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Std",
        meaning=(
            "Valve body 재질 표준 발행 기관. 4개 (ASTM/JIS/KS/EN)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Plug_Valve_Group.Matl_Std 옵션"
            " (closed set, 4개)."
        ),
        unique=None,
        relations=[
            "Matl_Code 의 std 키와 일치",
            "Rating 의 std 키와도 일치 — std-aware Rating 필터링",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Code",
        meaning=(
            "Valve body 의 구체 재질 규격 코드. **Cast grade** — Gate/Globe/"
            "Check 와 동일 옵션 패턴. ASTM (5): A216-WCB, A352-LCB/LCC,"
            " A351-CF8/CF8M. JIS (2): SCS13A/SCS14A. Cr-Mo cast (A217) 는"
            " 현재 미포함 (Plug valve 의 Cr-Mo 사용 드묾). KS/EN 항목은 추후."
        ),
        data_type="string (short code; e.g. A216-WCB / SCS13A)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Plug_Valve_Group.Matl_Code 옵션"
            " (closed set, 7개). KS/EN 항목은 추후 추가."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK), Matl_Category (의미적 정합) 와 함께 필터링",
            "Plug_Matl / Seat_Matl 과는 독립",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중"
            " Matl_Std 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Plug_Matl",
        meaning=(
            "Plug Valve plug (회전부) 재질. **Plug valve 고유 컬럼** — 다른"
            " valve 의 Trim_Matl 자리에 대응 (Plug valve 의 핵심 부품은 plug)."
            " 5종: F316, F304, 13Cr, Inconel-625, Monel-400. Body 와 다른 재질"
            " 선택 가능 — body 는 cast carbon steel, plug 는 F316 흔함."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Plug_Valve_Group.Plug_Matl 옵션"
            " (closed set, 5개)."
        ),
        unique=None,
        relations=[
            "Seat_Matl 와 호환 관행: plug + sleeve 의 재질 짝이 sealing 성능 결정",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Seat_Matl",
        meaning=(
            "Valve seat (plug 와 body 사이 sealing 면) 재질. 4종:"
            " PTFE (Non-Lubricated 의 sleeve 표준), Viton (rubber sleeve),"
            " F316 (metal seat, Lubricated 에 흔함), Stellite-6 (hardfacing"
            " metal seat). Non-Lubricated 의 경우 sleeve material 이 seat 역할"
            " (도메인 정의: sleeve = soft seat); Lubricated 의 경우 윤활제 film"
            " 이 일부 seat 역할 + metal seat 결합."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Plug_Valve_Group.Seat_Matl 옵션"
            " (closed set, 4개)."
        ),
        unique=None,
        relations=[
            "Plug_Matl 와 호환 관행 (위 Plug_Matl.relations 참조)",
            "Plug_Type 과 호환 관행: Lubricated → metal seat, Non-Lubricated →"
            " PTFE/Viton sleeve 가 통상 — 강제 검증 없음",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Rating",
        meaning=(
            "Valve 의 압력 등급. std-aware 필드 — Flange/Gasket/Gate/Globe/"
            "Check/Ball 과 옵션 풀 동일 (20개), ASTM 기준 표준은 ASME"
            " **B16.34** (Valve)."
            "\n - ASTM: 150# / 300# / 600# / 900# / 1500# / 2500#."
            "\n - JIS: 5K / 10K / 16K / 20K / 30K / 40K / 63K."
            "\n - KS: 5K / 10K / 16K / 20K / 30K / 40K / 63K."
        ),
        data_type="string (short code; ASTM NNN# 형식 / JIS·KS prefix+NK 형식)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Plug_Valve_Group.Rating 옵션"
            " (closed set, 20개)."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK) — std-aware 필터링의 1차 게이트",
            "Flange/Gate/Globe/Check/Ball 의 Rating 과 옵션 풀 동일",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중 Matl_Std"
            " 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="End_Type",
        meaning=(
            "Valve 단부 (end connection) 형식. 4종:"
            " BW (Butt Weld), SW (Socket Weld), TH (Threaded), FLG (Flanged)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Plug_Valve_Group.End_Type 옵션"
            " (closed set, 6개)."
        ),
        unique=None,
        relations=[
            "End_Type 이 FLGD* 일 때 Rating 이 상대 flange 와 짝이 되어야 정합"
            " (facing 은 End_Type 토큰에 포함). (별도 검증 영역)",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Operation",
        meaning=(
            "Valve 조작 방식. 5종:"
            " Manual (Handwheel), Lever (소구경 plug 의 표준),"
            " Wrench (Wrench Operated), Gear (Gear Operated — 대구경),"
            " Chain (Chain Operated — 높은 위치)."
            " Plug valve 는 90° 회전 조작이라 lever 가 흔하며, 대구경은 gear."
            " Motor / Pneumatic / Hydraulic 등 actuator 는 현재 미고려 (별도"
            " actuator 시트로 분리 검토)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Plug_Valve_Group.Operation 옵션"
            " (closed set, 5개)."
        ),
        unique=None,
        relations=[
            "Size1 과 호환 관행: ≤ 4\" 는 Lever, 6\"~ 는 Gear 가 흔함 — 강제 검증"
            " 없음",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Plug_Type",
        meaning=(
            "Plug Valve 의 윤활 방식. **Plug valve 고유 컬럼** — Ball valve 의"
            " Bore 와 유사한 도메인 핵심 분류. 2종:"
            " Lubricated (윤활제 주입형 — sealing 은 윤활제 film, 고압·고온),"
            " Non-Lubricated (PTFE 등 비금속 sleeve 가 plug 를 감싸 soft seat"
            " 역할; 'Sleeved' 라는 별칭은 본 시트에서 Non-Lubricated 와 동의어"
            " 로 통합). 빈 값 불허 — Plug valve 도메인 핵심 분류로 항상 명시."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Plug_Valve_Group.Plug_Type 옵션"
            " (closed set, 2개)."
        ),
        unique=None,
        relations=[
            "Seat_Matl 과 호환 관행: Lubricated → metal seat, Non-Lubricated →"
            " PTFE/Viton sleeve — 강제 검증 없음",
            "Rating 과 호환 관행: Lubricated 는 고온·고압, Non-Lubricated 는"
            " 일반 영역 — 강제 검증 없음",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Option_Code",
        meaning=(
            "Item_Code 변종/옵션 식별자. Pipe_Group.Option_Code 와 의미·형식"
            " 동일 — 3자리 숫자 텍스트, '001' = 해당 Class · Plug_Valve_Group"
            " 의 표준형."
        ),
        data_type="string (3자리 0-9 숫자 텍스트; e.g. '001')",
        required=True,
        format_constraint=(
            "정규식 ^\\d{3}$. data/field_values.json 의 Plug_Valve_Group.Option_Code"
            " 옵션 (closed set). 현재 '001' 한 개만 등록."
        ),
        unique=(
            "(Class_Name, Option_Code) 가 Plug_Valve_Group 시트 안에서 유일."
            " 다른 시트의 Option_Code 와는 독립."
        ),
        relations=[
            "(Class_Name, Option_Code) 가 Plug_Valve_Group 행의 자연 키",
            "Pipe_Group.Option_Code 와 동일 패턴",
        ],
        validation_location=(
            "Pipe_Group.Option_Code 와 동일 패턴 — 검증 모두 현재 미구현."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Remarks",
        meaning=(
            "행 단위 비고/설명 자유 텍스트. Pipe_Group.Remarks 와 의미·동작 동일."
            " Eccentric/Expanding 같은 특수 변종 명시, Multi-port 정보 (3-way/"
            "4-way), Actuator 정보 (Motor / Pneumatic 등 — 별도 시트 미구현"
            " 단계 동안 우회), 윤활제 종류 (Lubricated 의 경우) 등을 자유 입력."
        ),
        data_type="string (자유 텍스트, 빈 값 허용)",
        required=False,
        format_constraint=(
            "형식 강제 없음 — data/field_values.json 의 _meta.free_input_fields"
            " 에 'Remarks' 명시 (모든 시트 공통)."
        ),
        unique=None,
        relations=[
            "PMS description 합성의 마지막 토큰 — Pipe_Group.Remarks 와 동일 패턴",
        ],
        validation_location=(
            "검증 없음 (자유 입력). required 아님."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 자유 텍스트 입력 (Entry widget)"
        ),
        unit=None,
    ),
]


# ── Needle_Valve_Group ─────────────────────────────────────────────────────────
#
# Needle Valve (정밀 유량 조절용 instrumentation valve) — Globe valve 의 변종.
# Component 계층 13번째 시트. 원래 Globe_Valve_Group.Disc_Type 의 Needle 옵션
# 으로 처리했었으나 도메인 결정 (사용자) 으로 별도 시트로 분리.
#
# Globe_Valve_Group 과의 주요 차이:
#   - **Matl_Code = Forged grades** — Needle valve 는 instrumentation 영역이라
#     forged body 가 표준 (Globe valve 의 Cast grade A216-WCB 등과 다름).
#     ASTM: A105 / A350-LF2 / A182-F304/F316/F304L/F316L / A182-F11 / A182-F22
#     (Forged_Fitting_Group 과 동일 패턴). JIS: SF440A / SUS304-F / SUS316-F.
#   - **Disc_Type 컬럼은 Needle 1종 고정** — needle disc geometry 가 시트 자체
#     의 정체성. optional + 빈 값 허용 (Globe Disc_Type 패턴과 동일).
#   - **Item_Code = VN** (NEEDLE VALVE).
#
# Globe_Valve_Group 과 동일한 부분:
#   - 16 필드 구조 그대로 (Class_Name → Item_Code → Size1 → Body Matl →
#     Trim_Matl/Seat_Matl → Rating → End_Type → Bonnet_Stem → Operation →
#     Disc_Type → Option_Code → Remarks).
#   - Matl_Category 7종 (CS/LTCS/AS/SS/DSS/SDSS/Ni-Alloy).
#   - Trim_Matl 5종, Seat_Matl 4종 (PTFE/Viton/F316/Stellite-6 — PTFE seat 가
#     needle valve 에 흔함).
#   - Rating std-aware 20종 (ASTM 6 + JIS 7 + KS 7) — Globe 와 동일.
#   - End_Type 4종 (BW/SW/TH/FLG — TH 가 instrumentation 표준 흔함).
#   - Bonnet_Stem 7조합 (BB/WB/PSB/SB × OS&Y/NRS/ISRS 현실 조합) — Gate/Globe 동일.
#   - Operation 5종 (Manual/Lever/Wrench/Gear/Chain) — 일반적으로 소구경 Manual
#     이지만 옵션 풀은 일관성 유지.
#
# 도메인 표준:
#   - ASME B16.34 (Valve body/bonnet 표준)
#   - API 6D (Pipeline valve)
#   - ISO 15761 (Control valve testing)
#   - MSS SP-99 (Instrumentation valves and manifolds)
#
# 미고려 항목 (추후 도메인 합의 시 확장):
#   - Body Pattern (Straight / Angle / Multiport) — Swagelok / SSP 등 표준 옵션
#     인데 현재 미신설. 별도 컬럼 신설 후 도메인 합의 시 등록.
#   - Needle 고유 Bonnet 분류 (Integral / Union / Locked) — 현재 Globe 의 4종
#     공용. instrumentation 표준 분류로 별도 옵션 풀 검토 가능.
#   - Stem 형식 (Regulating / Vee / Sharp) — needle tip 정밀도.
#   - Pressure 단위 PSI (instrumentation 관행) — 현재 Rating 은 ASME Class 표기.
#   - Connection sizes ⅛" ~ 2" (instrumentation 표준) — Class_Define 의 size
#     범위에서 자연스럽게 처리.

NEEDLE_VALVE_GROUP_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="Class_Name",
        meaning=(
            "이 행이 소속될 Class 의 이름. Pipe_Group.Class_Name 과 의미·검증"
            " 모두 동일."
        ),
        data_type="string",
        required=True,
        format_constraint=(
            "공백 trim. Class_Define.Class_Name 행 집합 기준 일치 검사."
        ),
        unique=None,
        relations=[
            "Class_Define.Class_Name 으로 FK",
        ],
        validation_location=(
            "Pipe_Group.Class_Name 과 동일 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class_Define 행 목록)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Item_Code",
        meaning=(
            "Needle_Valve_Group 의 component 종류 식별자. 현재 'VN' (NEEDLE"
            " VALVE) 하나만 정의 — Needle valve 의 body pattern (Straight/"
            "Angle/Multiport) 구분은 별도 컬럼 신설 시 도메인 합의 후 처리."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/item_code_db.json 의 Needle_Valve_Group 행 (closed set, 현재"
            " 1개)."
        ),
        unique=None,
        relations=[
            "item_code_db.json Needle_Valve_Group 의 code 값 중 하나 (FK)",
            "PMS description prefix 합성: VN → NEEDLE VALVE",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set 옵션 강제)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — item_code_db 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size1_From",
        meaning=(
            "NPS/DN size 범위의 하한. Needle valve 는 instrumentation 영역이라"
            " ⅛\" ~ 2\" 범위가 표준이지만 옵션 풀 자체는 Class_Define 의 catalog"
            " 따라감."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size1_From <= Size1_To 강제 (행 단위 검증, 별도 작업)."
        ),
        unique=None,
        relations=[
            "Class_Define.Size_From / Size_To 범위 안",
        ],
        validation_location=(
            "Pipe_Group.Size_From 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Size1_To",
        meaning=(
            "NPS/DN size 범위의 상한. Size1_From 의 상한 짝."
        ),
        data_type="string (NPS or DN token)",
        required=True,
        format_constraint=(
            "Class_Define 의 Nominal_Size_System 기반 NPS/DN catalog."
            " Size1_From <= Size1_To 강제."
        ),
        unique=None,
        relations=[
            "(Size1_From, Size1_To) 의 상한",
        ],
        validation_location=(
            "Pipe_Group.Size_To 패턴."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — Class 의 size 범위)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Category",
        meaning=(
            "Needle valve body 재질의 대분류 카테고리. 7종 (Globe 와 동일):"
            " CS / LTCS / AS / SS / DSS / SDSS / Ni-Alloy."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Needle_Valve_Group.Matl_Category 옵션"
            " (closed set, 7개)."
        ),
        unique=None,
        relations=[
            "Matl_Std / Matl_Code 와 종속 체인 (Pipe_Group 패턴 동일)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Std",
        meaning=(
            "Needle valve body 재질 표준 발행 기관. 4개 (ASTM/JIS/KS/EN)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Needle_Valve_Group.Matl_Std 옵션"
            " (closed set, 4개)."
        ),
        unique=None,
        relations=[
            "Matl_Code 의 std 키와 일치",
            "Rating 의 std 키와도 일치 — std-aware Rating 필터링",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Matl_Code",
        meaning=(
            "Needle valve body 의 구체 재질 규격 코드. **Forged grade** —"
            " instrumentation 영역의 needle valve 표준 (Globe valve 의 Cast"
            " grade A216-WCB 등과 다름). ASTM (8): A105, A350-LF2, A182-F304/"
            "F316/F304L/F316L, A182-F11/F22. JIS (3): SF440A, SUS304-F,"
            " SUS316-F. KS/EN 항목은 추후 추가."
        ),
        data_type="string (short code; e.g. A105 / A182-F316)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Needle_Valve_Group.Matl_Code 옵션"
            " (closed set, 11개)."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK), Matl_Category (의미적 정합) 와 함께 필터링",
            "Matl_Code 의 category 키 ↔ Matl_Category 셀 일치"
            " (code_category_consistency rule)",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중"
            " Matl_Std 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Trim_Matl",
        meaning=(
            "Needle valve trim (stem/seat ring 등 내부 부품) 재질. 5종 (Globe"
            " 와 동일): F316 / F304 / 13Cr / Inconel-625 / Monel-400. Body 와"
            " 다른 재질 선택 가능 — body 는 forged carbon steel, trim 은 F316"
            " 흔함."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Needle_Valve_Group.Trim_Matl 옵션"
            " (closed set, 5개)."
        ),
        unique=None,
        relations=[
            "Seat_Matl 와 호환 관행: trim + seat 의 재질 짝이 sealing 성능 결정",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Seat_Matl",
        meaning=(
            "Valve seat (needle 과 body 사이 sealing 면) 재질. 4종 (Globe 와"
            " 동일): PTFE (soft seat, instrumentation 흔함), Viton (rubber"
            " seat), F316 (metal seat), Stellite-6 (hardfacing metal seat)."
            " Needle valve 는 PTFE seat 가 일반적이지만 고온·고압엔 metal"
            " seat 가 선호."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Needle_Valve_Group.Seat_Matl 옵션"
            " (closed set, 4개)."
        ),
        unique=None,
        relations=[
            "Trim_Matl 와 호환 관행 (위 Trim_Matl.relations 참조)",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Rating",
        meaning=(
            "Valve 의 압력 등급. std-aware 필드 — Globe 와 옵션 풀 동일 (20개),"
            " ASTM 기준 표준은 ASME **B16.34**."
            "\n - ASTM: 150# / 300# / 600# / 900# / 1500# / 2500#."
            "\n - JIS: 5K / 10K / 16K / 20K / 30K / 40K / 63K."
            "\n - KS: 5K / 10K / 16K / 20K / 30K / 40K / 63K."
            " Instrumentation needle valve 는 PSI 표기 (6000~20000 PSI) 가"
            " 흔하나 본 시트는 ASME Class 통일 (별도 PSI 단위 옵션 미신설)."
        ),
        data_type="string (short code; ASTM NNN# 형식 / JIS·KS prefix+NK 형식)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Needle_Valve_Group.Rating 옵션"
            " (closed set, 20개)."
        ),
        unique=None,
        relations=[
            "Matl_Std (FK) — std-aware 필터링의 1차 게이트",
            "Globe/Gate/Check/Ball/Plug 의 Rating 과 옵션 풀 동일",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set + std 필터)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션 중 Matl_Std"
            " 와 일치하는 항목만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="End_Type",
        meaning=(
            "Valve 단부 (end connection) 형식. 4종 (Globe 와 동일):"
            " BW (Butt Weld), SW (Socket Weld), TH (Threaded — NPT,"
            " instrumentation 표준 흔함), FLG (Flanged)."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Needle_Valve_Group.End_Type 옵션"
            " (closed set, 6개)."
        ),
        unique=None,
        relations=[
            "End_Type 이 FLGD* 일 때 Rating 이 상대 flange 와 짝이 되어야 정합"
            " (facing 은 End_Type 토큰에 포함). (별도 검증 영역)",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Bonnet_Stem",
        meaning=(
            "Valve bonnet 형식과 stem 구동 방식의 통합 분류 (Gate/Globe 와 동일"
            " 7조합): BB OS&Y / BB NRS / BB ISRS / WB OS&Y / PSB OS&Y / SB ISRS /"
            " SB NRS."
            " 본넷 BB=Bolted · WB=Welded · PSB=Pressure-Sealed · SB=Screwed;"
            " stem OS&Y=Outside Screw & Yoke · NRS=Non-Rising Stem ·"
            " ISRS=Inside Screw Rising Stem."
            " Needle valve 고유 분류 (Integral / Union / Locked-Bonnet) 는"
            " 별도 도메인 합의 후 등록."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Needle_Valve_Group.Bonnet_Stem 옵션"
            " (closed set, 7개)."
        ),
        unique=None,
        relations=[
            "Bonnet_Stem=PSB OS&Y 일 때 Rating 고압 (1500# 이상) 흔함 — 강제"
            " 검증 없음",
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Operation",
        meaning=(
            "Valve 조작 방식. 5종 (Globe 와 동일):"
            " Manual (Handwheel — 표준), Lever, Wrench, Gear, Chain."
            " Instrumentation needle valve 는 거의 Manual 이지만 옵션 풀은"
            " 일관성 유지."
        ),
        data_type="string (short code)",
        required=True,
        format_constraint=(
            "data/field_values.json 의 Needle_Valve_Group.Operation 옵션"
            " (closed set, 5개)."
        ),
        unique=None,
        relations=[
            "PMS description 에 합성",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Disc_Type",
        meaning=(
            "Needle valve disc 형태. **Needle 1종 고정** — needle disc 가"
            " 시트 자체의 정체성이라 다른 옵션 없음. 빈 값 허용 (PMS"
            " description 에 명시 안 하는 케이스). Globe Disc_Type 패턴과"
            " 동일 (optional)."
        ),
        data_type="string (short code)",
        required=False,
        format_constraint=(
            "data/field_values.json 의 Needle_Valve_Group.Disc_Type 옵션"
            " (closed set, 1개)."
        ),
        unique=None,
        relations=[
            "PMS description 에 합성 (값 있을 때만)",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set)."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Option_Code",
        meaning=(
            "Item_Code 변종/옵션 식별자. Pipe_Group.Option_Code 와 의미·형식"
            " 동일 — 3자리 숫자 텍스트, '001' = 해당 Class · Needle_Valve_Group"
            " 의 표준형."
        ),
        data_type="string (3자리 0-9 숫자 텍스트; e.g. '001')",
        required=True,
        format_constraint=(
            "정규식 ^\\d{3}$. data/field_values.json 의 Needle_Valve_Group."
            "Option_Code 옵션 (closed set). 현재 '001' 한 개만 등록."
        ),
        unique=(
            "(Class_Name, Option_Code) 가 Needle_Valve_Group 시트 안에서 유일."
            " 다른 시트의 Option_Code 와는 독립."
        ),
        relations=[
            "(Class_Name, Option_Code) 가 Needle_Valve_Group 행의 자연 키",
            "Pipe_Group.Option_Code 와 동일 패턴",
        ],
        validation_location=(
            "Pipe_Group.Option_Code 와 동일 패턴 — 검증 모두 현재 미구현."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 콤보박스 (readonly — DB 옵션만)"
        ),
        unit=None,
    ),
    FieldDefinition(
        name="Remarks",
        meaning=(
            "행 단위 비고/설명 자유 텍스트. Pipe_Group.Remarks 와 의미·동작"
            " 동일. Body pattern (Straight/Angle/Multiport), Stem 형식"
            " (Regulating/Vee/Sharp), Bonnet 변종 (Integral/Union/Locked),"
            " PSI 단위 압력 등 별도 컬럼 미신설 항목은 자유 입력."
        ),
        data_type="string (자유 텍스트, 빈 값 허용)",
        required=False,
        format_constraint=(
            "형식 강제 없음 — data/field_values.json 의 _meta.free_input_fields"
            " 에 'Remarks' 명시 (모든 시트 공통)."
        ),
        unique=None,
        relations=[
            "PMS description 합성의 마지막 토큰 — Pipe_Group.Remarks 와 동일 패턴",
        ],
        validation_location=(
            "검증 없음 (자유 입력). required 아님."
        ),
        input_method=(
            "wizard 컴포넌트 dialog 의 자유 텍스트 입력 (Entry widget)"
        ),
        unit=None,
    ),
]


# ── 그룹 레지스트리 + 도출 헬퍼 (SSOT 진입점) ─────────────────────────────────
# 다른 모듈(template_generator.COMPONENT_GROUP_DEFS, data_defaults.DEFAULT_COMPONENT_MAPPING)
# 은 이 레지스트리에서 헤더/필수 필드를 도출한다. 헤더·필수의 정의는 오직 여기(SSOT).
GROUPS: dict[str, list[FieldDefinition]] = {
    "Pipe_Group": PIPE_GROUP_FIELDS,
    "Forged_Fitting_Group": FORGED_FITTING_GROUP_FIELDS,
    "Wrought_Fitting_Group": WROUGHT_FITTING_GROUP_FIELDS,
    "Flange_Group": FLANGE_GROUP_FIELDS,
    "Gasket_Group": GASKET_GROUP_FIELDS,
    "Bolt_Group": BOLT_GROUP_FIELDS,
    "Gate_Valve_Group": GATE_VALVE_GROUP_FIELDS,
    "Globe_Valve_Group": GLOBE_VALVE_GROUP_FIELDS,
    "Check_Valve_Group": CHECK_VALVE_GROUP_FIELDS,
    "Ball_Valve_Group": BALL_VALVE_GROUP_FIELDS,
    "Butterfly_Valve_Group": BUTTERFLY_VALVE_GROUP_FIELDS,
    "Plug_Valve_Group": PLUG_VALVE_GROUP_FIELDS,
    "Needle_Valve_Group": NEEDLE_VALVE_GROUP_FIELDS,
}


def group_fields(sheet: str) -> list[FieldDefinition]:
    """그룹의 FieldDefinition 목록 (컬럼 순서)."""
    return GROUPS[sheet]


def headers(sheet: str) -> list[str]:
    """그룹의 헤더(컬럼명) 목록 — 컬럼 순서대로."""
    return [fd.name for fd in GROUPS[sheet]]


def required_fields(sheet: str) -> list[str]:
    """required=True 인 필드명 목록 (required_non_empty 도출원)."""
    return [fd.name for fd in GROUPS[sheet] if fd.required]


def _grouped_conditional(sheet: str, attr: str, require_key: str) -> list[dict]:
    """attr(conditional_*_when) 를 (when_field, when_values) 별로 묶어 mapping 항목 생성.
    같은 조건을 공유하는 필드들은 한 항목의 require 리스트로 모은다."""
    acc: dict[tuple, list[str]] = {}
    order: list[tuple] = []
    for fd in GROUPS[sheet]:
        spec = getattr(fd, attr)
        if not spec:
            continue
        key = (spec["field"], tuple(spec["values"]))
        if key not in acc:
            acc[key] = []
            order.append(key)
        acc[key].append(fd.name)
    out: list[dict] = []
    for (wfield, wvalues) in order:
        out.append({"when_field": wfield, "when_values": list(wvalues), require_key: acc[(wfield, wvalues)]})
    return out


def conditional_required(sheet: str) -> list[dict]:
    """conditional_required_when 도출 — DEFAULT_COMPONENT_MAPPING.conditional_required."""
    return _grouped_conditional(sheet, "conditional_required_when", "require_non_empty")


def conditional_empty(sheet: str) -> list[dict]:
    """conditional_empty_when 도출 — DEFAULT_COMPONENT_MAPPING.conditional_empty."""
    return _grouped_conditional(sheet, "conditional_empty_when", "require_empty")


def code_category_consistency(sheet: str) -> list[dict]:
    """(code_field, category_field) 짝이 둘 다 존재하면 일관성 규칙 도출.
    Matl_Code↔Matl_Category 외에 Bolt_Matl_Code↔Bolt_Matl_Category 도 포함."""
    names = {fd.name for fd in GROUPS[sheet]}
    pairs = [
        ("Matl_Code", "Matl_Category"),
        ("Bolt_Matl_Code", "Bolt_Matl_Category"),
    ]
    return [
        {"code_field": c, "category_field": cat}
        for c, cat in pairs
        if c in names and cat in names
    ]


# ── 값(드롭다운) 데이터 접근 façade ────────────────────────────────────────────
# 값 자체는 데이터 파일(field_values.json / item_code_db.json)에 두되, 그 파일을
# 직접 읽는 런타임 코드는 여기 하나뿐이다. 다른 모듈은 이 함수들로만 값을 얻는다
# ("다른 모듈은 이 스키마만 참조한다"). '_' 접두 키(_meta 등)는 제외.
@lru_cache(maxsize=1)
def field_values_db() -> dict[str, dict[str, list[dict[str, str]]]]:
    path = config.field_values_db_path()
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f) or {}
    return {k: v for k, v in raw.items() if not k.startswith("_")}


@lru_cache(maxsize=1)
def item_code_db() -> dict[str, list[dict[str, str]]]:
    path = config.item_code_db_json_path()
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f) or {}
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def field_value_options(sheet: str, field_name: str) -> list[dict[str, str]]:
    """그룹·필드의 드롭다운 옵션 목록 (short/long/std/category 등 raw dict)."""
    return (field_values_db().get(sheet) or {}).get(field_name) or []


def item_code_entries(sheet: str) -> list[dict[str, str]]:
    """그룹의 Item_Code 항목 목록 (code/code_name/shape)."""
    return item_code_db().get(sheet) or []


# ── 재질 카테고리 family (큰 분류) ─────────────────────────────────────────────
# 볼트↔너트처럼 "designation 은 달라도 큰 분류는 같아야" 하는 검증/필터에 사용.
# 예: B7(AS) 볼트 ↔ 2H(CS) 너트 — 둘 다 ferrous-carbon family 라 호환.
_CATEGORY_FAMILY: dict[str, str] = {
    "CS": "ferrous-carbon",
    "LTCS": "ferrous-carbon",
    "AS": "ferrous-carbon",
    "SS": "stainless",
    "DSS": "stainless",
    "SDSS": "stainless",
    "Ni-Alloy": "ni-alloy",
    "Cu-Alloy": "cu-alloy",
    "GI": "galvanized",
    "CI": "cast-iron",
}


def category_family(category: str) -> str:
    """카테고리 short → 큰 분류 family. 미등록은 자기 자신(보수적)."""
    c = (category or "").strip()
    return _CATEGORY_FAMILY.get(c, c)
