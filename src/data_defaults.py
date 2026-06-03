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
            ],
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Forged_Fitting_Group": {
            "required_non_empty": [
                "Class_Name",
                "Item_Code",
                "Size_From",
                "Size_To",
                "Matl_Category",
                "Matl_Std",
                "Matl_Code",
                "Rating",
                "End_Type",
                "Option_Code",
            ],
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Wrought_Fitting_Group": {
            "required_non_empty": [
                "Class_Name",
                "Item_Code",
                "Size_From",
                "Size_To",
                "Matl_Category",
                "Matl_Std",
                "Matl_Code",
                "Manufacturing_Method",
                "End_Type",
                "Option_Code",
            ],
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Flange_Group": {
            "required_non_empty": [
                "Class_Name",
                "Item_Code",
                "Size1_From",
                "Size1_To",
            ],
            "conditional_required": [
                {
                    "when_field": "Item_Code",
                    "when_values": ["FR"],
                    "require_non_empty": ["Size2_From", "Size2_To"],
                },
            ],
            "conditional_empty": [
                {
                    "when_field": "Item_Code",
                    "when_values": ["F", "FB", "F8", "FBS"],
                    "require_empty": ["Size2_From", "Size2_To"],
                },
            ],
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Gate_Valve_Group": {
            "required_non_empty": [
                "Class_Name",
                "Item_Code",
                "Size1_From",
                "Size1_To",
                "Matl_Category",
                "Matl_Std",
                "Matl_Code",
                "Trim_Matl",
                "Seat_Matl",
                "Rating",
                "End_Type",
                "Bonnet_Type",
                "Operation",
                "Option_Code",
            ],
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Globe_Valve_Group": {
            "required_non_empty": [
                "Class_Name",
                "Item_Code",
                "Size1_From",
                "Size1_To",
                "Matl_Category",
                "Matl_Std",
                "Matl_Code",
                "Trim_Matl",
                "Seat_Matl",
                "Rating",
                "End_Type",
                "Bonnet_Type",
                "Operation",
                "Option_Code",
            ],
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Check_Valve_Group": {
            "required_non_empty": [
                "Class_Name",
                "Item_Code",
                "Size1_From",
                "Size1_To",
                "Matl_Category",
                "Matl_Std",
                "Matl_Code",
                "Trim_Matl",
                "Seat_Matl",
                "Rating",
                "End_Type",
                "Option_Code",
            ],
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Ball_Valve_Group": {
            "required_non_empty": [
                "Class_Name",
                "Item_Code",
                "Size1_From",
                "Size1_To",
                "Matl_Category",
                "Matl_Std",
                "Matl_Code",
                "Trim_Matl",
                "Seat_Matl",
                "Rating",
                "End_Type",
                "Bore",
                "Operation",
                "Option_Code",
            ],
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Butterfly_Valve_Group": {
            "required_non_empty": [
                "Class_Name",
                "Item_Code",
                "Size1_From",
                "Size1_To",
                "Matl_Category",
                "Matl_Std",
                "Matl_Code",
                "Disc_Matl",
                "Seat_Matl",
                "Rating",
                "End_Type",
                "Body_Type",
                "Operation",
                "Option_Code",
            ],
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Plug_Valve_Group": {
            "required_non_empty": [
                "Class_Name",
                "Item_Code",
                "Size1_From",
                "Size1_To",
                "Matl_Category",
                "Matl_Std",
                "Matl_Code",
                "Plug_Matl",
                "Seat_Matl",
                "Rating",
                "End_Type",
                "Operation",
                "Plug_Type",
                "Option_Code",
            ],
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
        },
        "Needle_Valve_Group": {
            "required_non_empty": [
                "Class_Name",
                "Item_Code",
                "Size1_From",
                "Size1_To",
                "Matl_Category",
                "Matl_Std",
                "Matl_Code",
                "Trim_Matl",
                "Seat_Matl",
                "Rating",
                "End_Type",
                "Bonnet_Type",
                "Operation",
                "Option_Code",
            ],
            "code_category_consistency": [
                {"code_field": "Matl_Code", "category_field": "Matl_Category"},
            ],
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
                "Thickness",
            ],
            "conditional_required": [
                {
                    "when_field": "Gasket_Type",
                    "when_values": ["SW"],
                    "require_non_empty": ["Material_Secondary"],
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
                "Bolt_Matl_Category",
                "Bolt_Matl_Std",
                "Bolt_Matl_Code",
                "Nut_Type",
                "Nut_Matl_Category",
                "Nut_Matl_Std",
                "Nut_Matl_Code",
                "Bolt_Length_Table",
                "Option_Code",
            ]
        },
    },
}
