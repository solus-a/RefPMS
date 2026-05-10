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
            "data/field_values_db.json 의 Pipe_Group.Matl_Category 옵션"
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
]
