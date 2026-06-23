"""템플릿·데이터 보조 파일 생성용 기본 내용 (JSON 직렬화)."""

from __future__ import annotations

import domain_schema as _domain_schema

DEFAULT_CLASS_MATERIAL_MAPPING: dict = {
    "description": "Class_Base_Material 키(로드 시 대문자) → 부품 Mat 문자열에 포함될 허용 토큰.",
    "base_material_allowlist": {
        "KCS": [
            "A106",
            "A105",
            "A234",
            "A333",
            "A672",
            "A420",
            "A694",
            "A53",
        ]
    },
}

# required_non_empty 는 여기서 정의하지 않는다 — domain_schema(SSOT)의 required 플래그에서
# 아래 루프로 도출한다. 이 dict 에는 도출 불가한 규칙(조건부/일관성)만 직접 정의한다.
DEFAULT_COMPONENT_MAPPING: dict = {
    "version": 1,
    "description": (
        "부품군(시트)별 템플릿 행 검증 규칙. 컬럼이 시트에 없으면 해당 규칙은 건너뜀. "
        "required_non_empty 는 domain_schema(SSOT)의 required 플래그에서 도출 (이중정의 방지)."
    ),
    "sheets": {
        "Pipe_Group": {
            "conditional_required": [
                {"when_field": "Item_Code", "when_values": ["JN"], "require_non_empty": ["Length"]},
            ],
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Forged_Fitting_Group": {
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Wrought_Fitting_Group": {
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Flange_Group": {
            "conditional_required": [
                {"when_field": "Item_Code", "when_values": ["FR"], "require_non_empty": ["Size2_From", "Size2_To"]},
            ],
            "conditional_empty": [
                {"when_field": "Item_Code", "when_values": ["F", "FB", "F8", "FBS"], "require_empty": ["Size2_From", "Size2_To"]},
            ],
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Gate_Valve_Group": {
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Globe_Valve_Group": {
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Check_Valve_Group": {
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Ball_Valve_Group": {
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Butterfly_Valve_Group": {
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Plug_Valve_Group": {
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Needle_Valve_Group": {
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Gasket_Group": {
            "conditional_required": [
                {"when_field": "Gasket_Type", "when_values": ["SW"], "require_non_empty": ["Material_Secondary"]},
            ],
        },
        "Bolt_Group": {},
    },
}

# required_non_empty 도출 — domain_schema(SSOT)가 헤더·필수의 단일 정의처.
for _sheet, _rules in DEFAULT_COMPONENT_MAPPING["sheets"].items():
    _rules["required_non_empty"] = _domain_schema.required_fields(_sheet)
