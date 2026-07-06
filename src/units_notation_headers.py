"""Class_Define column headers — storage keys (unit-free) vs display headers (with [unit])."""

from __future__ import annotations

import domain_schema as _domain_schema

# 컬럼명·순서의 SSOT 는 domain_schema.CLASS_DEFINE_FIELDS — 여기서 도출한다.
CLASS_DEFINE_STORAGE_KEYS: tuple[str, ...] = tuple(_domain_schema.class_define_headers())


_TEMPERATURE_KEYS: frozenset[str] = frozenset({
    "Design_Temperature_From",
    "Design_Temperature_To",
})

_PRESSURE_KEYS: frozenset[str] = frozenset({
    "Design_Pressure_From",
    "Design_Pressure_To",
})


def bracket_unit_header(base_column_name: str, unit_display: str) -> str:
    u = unit_display.strip()
    if not u:
        return base_column_name
    return f"{base_column_name} [{u}]"


def class_define_storage_headers() -> list[str]:
    """Domain (unit-free) keys used inside ClassLevelBundle.class_define_rows."""
    return list(CLASS_DEFINE_STORAGE_KEYS)


def class_define_display_headers(
    design_temperature_unit: str, design_pressure_unit: str
) -> list[str]:
    """xlsx column headers — temperature/pressure keys carry [unit] notation."""
    out: list[str] = []
    for key in CLASS_DEFINE_STORAGE_KEYS:
        if key in _TEMPERATURE_KEYS:
            out.append(bracket_unit_header(key, design_temperature_unit))
        elif key in _PRESSURE_KEYS:
            out.append(bracket_unit_header(key, design_pressure_unit))
        else:
            out.append(key)
    return out


def class_define_headers(design_temperature_unit: str, design_pressure_unit: str) -> list[str]:
    """Backward-compatible alias for :func:`class_define_display_headers`."""
    return class_define_display_headers(design_temperature_unit, design_pressure_unit)


def class_define_storage_to_display_key(
    storage_key: str, design_temperature_unit: str, design_pressure_unit: str
) -> str:
    if storage_key in _TEMPERATURE_KEYS:
        return bracket_unit_header(storage_key, design_temperature_unit)
    if storage_key in _PRESSURE_KEYS:
        return bracket_unit_header(storage_key, design_pressure_unit)
    return storage_key


def class_define_storage_to_display_row(
    row: dict[str, str],
    design_temperature_unit: str,
    design_pressure_unit: str,
) -> dict[str, str]:
    """Convert a row keyed by storage keys to a row keyed by display headers (xlsx export)."""
    return {
        class_define_storage_to_display_key(
            key, design_temperature_unit, design_pressure_unit
        ): str(row.get(key, "") or "")
        for key in CLASS_DEFINE_STORAGE_KEYS
    }


def class_define_display_to_storage_row(
    row: dict[str, str],
    design_temperature_unit: str,
    design_pressure_unit: str,
) -> dict[str, str]:
    """Convert a row keyed by display headers to a row keyed by storage keys (xlsx import)."""
    return {
        key: str(
            row.get(
                class_define_storage_to_display_key(
                    key, design_temperature_unit, design_pressure_unit
                ),
                "",
            )
            or ""
        )
        for key in CLASS_DEFINE_STORAGE_KEYS
    }


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
        "Size_From": "size_from",
        "Size_To": "size_to",
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
