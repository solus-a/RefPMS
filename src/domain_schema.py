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

from dataclasses import dataclass, field
from typing import Optional


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
            " Fitting/Reducer 시트는 End_Type 대신 End_Type_1 / End_Type_2 로"
            " 양 끝을 별도 컬럼에 두며 PMS 엔진이 dimensional standard 결정에 사용."
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
            "PMS 엔진의 Fitting/Reducer 처리에서는 End_Type_1/_2 로 dimensional"
            " standard (ASME B16.9 / B16.11 등) 결정. Pipe_Group 의 End_Type 은"
            " description 출력 전용.",
        ],
        validation_location=(
            "wizard 컴포넌트 dialog 의 콤보박스 (closed set 옵션 강제)."
            " PMS 엔진은 ['End_Type_1', 'End_Type'] fallback 으로 옛 헤더 / 단일"
            " End_Type 시트도 받음."
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
    ),
]
