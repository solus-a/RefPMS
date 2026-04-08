"""템플릿·데이터 보조 파일 생성용 기본 내용 (JSON 직렬화)."""

from __future__ import annotations

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

DEFAULT_COMPONENT_MAPPING: dict = {
    "version": 1,
    "description": "부품군(시트)별 템플릿 행 검증 규칙. 컬럼이 시트에 없으면 해당 규칙은 건너뜀.",
    "sheets": {
        "Pipe_Group": {
            "required_non_empty": [
                "Class_Name",
                "Item_Code",
                "Size_From",
                "Size_To",
            ]
        },
        "Fitting_Group": {
            "required_non_empty": [
                "Class_Name",
                "Item_Code",
                "Size_From",
                "Size_To",
            ],
            "xor_at_most_one_filled": [["Schedule", "Rating"]],
        },
        "Flange_Group": {
            "required_non_empty": [
                "Class_Name",
                "Item_Code",
                "Size1_From",
                "Size1_To",
            ]
        },
        "Valve": {
            "required_non_empty": [
                "Class_Name",
                "Item_Code",
                "Size_From",
                "Size_To",
            ]
        },
        "Gasket_Group": {
            "required_non_empty": [
                "Class_Name",
                "Item_Code",
                "Size_From",
                "Size_To",
                "Gasket_Type",
                "Material_Primary",
                "Rating",
                "Facing",
                "Dim_Standard",
            ],
            "conditional_required": [
                {
                    "when_field": "Gasket_Type",
                    "when_values": ["SPIRAL WOUND"],
                    "require_non_empty": [
                        "Material_Secondary",
                        "Material_Inner_Ring",
                        "Material_Outer_Ring",
                        "Thickness",
                    ],
                },
                {
                    "when_field": "Gasket_Type",
                    "when_values": [
                        "ENVELOPED",
                        "JACKETED",
                        "COMPRESSED NON-ASBESTOS",
                    ],
                    "require_non_empty": ["Material_Secondary", "Thickness"],
                },
                {
                    "when_field": "Gasket_Type",
                    "when_values": ["RUBBER", "SOLID"],
                    "require_non_empty": ["Thickness"],
                },
                {
                    "when_field": "Gasket_Type",
                    "when_values": ["RING JOINT OVAL", "RING JOINT OCTAGONAL"],
                    "require_non_empty": ["Remarks"],
                },
            ],
        },
        "Bolt_Group": {
            "required_non_empty": [
                "Class_Name",
                "Item_Code",
                "Size_From",
                "Size_To",
                "Bolt_Type",
                "Bolt_Mat_Code",
                "Nut_Type",
                "Nut_Mat_Code",
                "Bolt_Dim_Standard",
                "Nut_Dim_Standard",
            ]
        },
    },
}
