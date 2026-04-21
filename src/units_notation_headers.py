"""Class Template 전역 단위 → Class_Define 컬럼 헤더 (``[unit]`` notation)."""

from __future__ import annotations


def bracket_unit_header(base_column_name: str, unit_display: str) -> str:
    u = unit_display.strip()
    if not u:
        return base_column_name
    return f"{base_column_name} [{u}]"


def class_define_headers(design_temperature_unit: str, design_pressure_unit: str) -> list[str]:
    t = design_temperature_unit
    p = design_pressure_unit
    return [
        "Revision_No",
        "Class_Name",
        "Nominal_Size_System",
        "Design_Code",
        "Class_Base_Material",
        "Class_Rating",
        "Corrosion_Allowance",
        bracket_unit_header("Design_Temperature_From", t),
        bracket_unit_header("Design_Temperature_To", t),
        bracket_unit_header("Design_Pressure_From", p),
        bracket_unit_header("Design_Pressure_To", p),
        "Fluid_Service",
        "Branch_Table_1",
        "Branch_Table_2",
        "Reducing_Table_1",
        "Reducing_Table_2",
        "Global_Special_Req",
        "Remarks",
    ]


def class_define_excel_to_spec_key(
    design_temperature_unit: str, design_pressure_unit: str
) -> dict[str, str]:
    t = design_temperature_unit
    p = design_pressure_unit
    tf = bracket_unit_header("Design_Temperature_From", t)
    tt = bracket_unit_header("Design_Temperature_To", t)
    pf = bracket_unit_header("Design_Pressure_From", p)
    pt = bracket_unit_header("Design_Pressure_To", p)
    return {
        "Class_Name": "class_name",
        "Revision_No": "revision_no",
        "Nominal_Size_System": "nominal_size_system",
        "Design_Code": "design_code",
        "Class_Base_Material": "class_base_material",
        "Class_Rating": "class_rating",
        "Corrosion_Allowance": "corrosion_allowance",
        tf: "design_temperature_from",
        tt: "design_temperature_to",
        pf: "design_pressure_from",
        pt: "design_pressure_to",
        "Fluid_Service": "fluid_service",
        "Branch_Table_1": "branch_table_1",
        "Branch_Table_2": "branch_table_2",
        "Reducing_Table_1": "reducing_table_1",
        "Reducing_Table_2": "reducing_table_2",
        "Global_Special_Req": "global_special_req",
        "Remarks": "remarks",
    }
