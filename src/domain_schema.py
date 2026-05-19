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
            " Required 검증: class_level_model.PIPE_GROUP_REQUIRED_FIELDS 에"
            " 'Option_Code' 포함 (등록 완료)."
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
            " class_level_model.PIPE_GROUP_REQUIRED_FIELDS 미포함."
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
