"""Layer 2: 클래스(재질 등급) 기술 봉투 — Class_Define 시트에서 ClassSpec 로드 및 제약 힌트."""

from __future__ import annotations

import json
from typing import Any, Optional, TypedDict

import config

from excel_sheet_utils import (
    build_header_index,
    detect_header_row,
    get_cell_text,
    pick_first_non_empty,
    to_text,
)
from units_notation_headers import class_define_excel_to_spec_key

CLASS_DEFINE_REQUIRED_HEADERS = ["Class_Name"]

VALVE_SHEET_NAMES = frozenset(
    {
        "Gate_Valve_Group",
        "Globe_Valve_Group",
        "Check_Valve_Group",
        "Ball_Valve_Group",
        "Butterfly_Valve_Group",
        "Plug_Valve_Group",
        "Needle_Valve_Group",
    }
)


def _class_define_excel_to_spec_key(workbook) -> dict[str, str]:
    """Class_Define 엑셀 헤더 → ClassSpec 키 매핑. 단위 헤더는 워크북의 Unit_System 시트에서 결정."""
    from class_level_model import read_global_settings_from_workbook

    gs = read_global_settings_from_workbook(workbook)
    return class_define_excel_to_spec_key(gs.design_temperature_unit, gs.design_pressure_unit)


class ClassSpec(TypedDict, total=False):
    class_name: str
    revision_no: str
    design_code: str
    nominal_size_system: str
    size_from: str
    size_to: str
    class_base_material: str
    class_rating: str
    corrosion_allowance: str
    design_temperature_from: str
    design_temperature_to: str
    design_pressure_from: str
    design_pressure_to: str
    fluid_service: str
    branch_table_1: str
    branch_table_2: str
    reducing_table_1: str
    reducing_table_2: str
    global_special_req: str
    remarks: str


_material_allowlist_cache: Optional[dict[str, list[str]]] = None


def _load_base_material_allowlist() -> dict[str, list[str]]:
    """data/class_material_mapping.json 의 base_material_allowlist (키 대문자)."""
    global _material_allowlist_cache
    if _material_allowlist_cache is not None:
        return _material_allowlist_cache

    path = config.class_material_mapping_path()
    out: dict[str, list[str]] = {}
    if path.exists():
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            raw = data.get("base_material_allowlist") or {}
            if isinstance(raw, dict):
                for k, v in raw.items():
                    key = to_text(k).upper()
                    if isinstance(v, list):
                        out[key] = [to_text(x) for x in v if to_text(x)]
                    else:
                        out[key] = []
        except (OSError, json.JSONDecodeError, TypeError):
            out = {}
    _material_allowlist_cache = out
    return out


def clear_material_allowlist_cache() -> None:
    global _material_allowlist_cache
    _material_allowlist_cache = None


def load_class_specs_from_workbook(workbook) -> dict[str, ClassSpec]:
    """Class_Define 시트에서 클래스별 ClassSpec dict를 구성합니다."""
    if "Class_Define" not in workbook.sheetnames:
        return {}

    ws = workbook["Class_Define"]
    try:
        header_row = detect_header_row(ws, CLASS_DEFINE_REQUIRED_HEADERS)
    except ValueError:
        return {}

    header_to_col = build_header_index(ws, header_row)
    excel_to_key = _class_define_excel_to_spec_key(workbook)
    out: dict[str, ClassSpec] = {}

    for row_idx in range(header_row + 1, ws.max_row + 1):
        name = get_cell_text(ws, row_idx, header_to_col, "Class_Name")
        if not name:
            continue
        spec: ClassSpec = {"class_name": name}
        for excel_header, key in excel_to_key.items():
            if excel_header == "Class_Name":
                continue
            if excel_header not in header_to_col:
                continue
            val = get_cell_text(ws, row_idx, header_to_col, excel_header)
            if val:
                spec[key] = val  # type: ignore[literal-required]
        out[name] = spec

    return out


_STORAGE_KEY_TO_SPEC_KEY: dict[str, str] = {
    "Class_Name": "class_name",
    "Revision_No": "revision_no",
    "Nominal_Size_System": "nominal_size_system",
    "Size_From": "size_from",
    "Size_To": "size_to",
    "Design_Code": "design_code",
    "Class_Base_Material": "class_base_material",
    "Class_Rating": "class_rating",
    "Corrosion_Allowance": "corrosion_allowance",
    "Design_Temperature_From": "design_temperature_from",
    "Design_Temperature_To": "design_temperature_to",
    "Design_Pressure_From": "design_pressure_from",
    "Design_Pressure_To": "design_pressure_to",
    "Fluid_Service": "fluid_service",
    "Branch_Table_1": "branch_table_1",
    "Branch_Table_2": "branch_table_2",
    "Reducing_Table_1": "reducing_table_1",
    "Reducing_Table_2": "reducing_table_2",
    "Global_Special_Req": "global_special_req",
    "Remarks": "remarks",
}


def load_class_specs_from_bundle(bundle) -> dict[str, ClassSpec]:
    """ClassLevelBundle.class_define_rows 에서 클래스별 ClassSpec dict를 구성합니다.

    storage 키 기반 row dict 를 spec key (snake_case) 로 변환합니다.
    workbook 기반 :func:`load_class_specs_from_workbook` 와 결과 동등.
    """
    out: dict[str, ClassSpec] = {}
    for row in bundle.class_define_rows:
        name = (row.get("Class_Name") or "").strip()
        if not name:
            continue
        spec: ClassSpec = {"class_name": name}
        for storage_key, spec_key in _STORAGE_KEY_TO_SPEC_KEY.items():
            if storage_key == "Class_Name":
                continue
            val = (row.get(storage_key) or "").strip()
            if val:
                spec[spec_key] = val  # type: ignore[literal-required]
        out[name] = spec
    return out


def corrosion_allowance_validation_messages(workbook) -> tuple[list[str], list[str]]:
    """
    Class_Define.Corrosion_Allowance 검증.
    반환: (errors, warnings)
    - 빈값은 validation_policy.corrosion_allowance.empty_value_policy에 따라 warning/error
    - 비어있지 않은 값은 숫자여야 함
    """
    errors: list[str] = []
    warnings: list[str] = []
    if "Class_Define" not in workbook.sheetnames:
        return errors, warnings

    ws = workbook["Class_Define"]
    required = ["Class_Name", "Corrosion_Allowance"]
    try:
        header_row = detect_header_row(ws, required)
    except ValueError:
        return errors, warnings
    header_to_col = build_header_index(ws, header_row)
    if any(h not in header_to_col for h in required):
        return errors, warnings

    from class_level_model import read_global_settings_from_workbook

    gs = read_global_settings_from_workbook(workbook)
    unit_system = (gs.unit_system or "SI").strip() or "SI"
    ca_unit = "inch" if unit_system == "US Customary" else "mm"
    empty_policy = str(
        config.config_manager.get(
            "validation_policy.corrosion_allowance.empty_value_policy",
            "warning",
        )
        or "warning"
    ).strip().lower()

    for row_idx in range(header_row + 1, ws.max_row + 1):
        class_name = get_cell_text(ws, row_idx, header_to_col, "Class_Name")
        if not class_name:
            continue
        ca_raw = get_cell_text(ws, row_idx, header_to_col, "Corrosion_Allowance")
        if not ca_raw:
            msg = (
                f"Class_Define row {row_idx} Class {class_name}: "
                f"Corrosion_Allowance is empty ({ca_unit})."
            )
            if empty_policy == "error":
                errors.append(msg)
            else:
                warnings.append(msg)
            continue
        try:
            float(ca_raw)
        except ValueError:
            errors.append(
                f"Class_Define row {row_idx} Class {class_name}: "
                f"Corrosion_Allowance must be numeric; got {ca_raw!r}."
            )
    return errors, warnings


# (Rating 정합 검사는 폐지 — 도메인 결정: 한 Piping Class 안에 다른 rating 의
#  component 가 있는 것은 정상이다. 예: CL150 class 에 CL300 component —
#  CL300 class 배관과의 연결부용. 이종 규격(ASME/JIS/KS) 혼용도 마찬가지로 정상.
#  Class_Rating 은 class 의 대표 등급일 뿐 component rating 을 제약하지 않는다.)


def base_material_hint_message(
    part_mat: str,
    class_base: str,
    allowlist: Optional[dict[str, list[str]]] = None,
) -> Optional[str]:
    """
    Class_Base_Material 대비 부품 재질 힌트.
    data/class_material_mapping.json 에 키가 있으면 allowlist 토큰(부분 문자열)으로만 허용 판단.
    키가 없으면 기존 단순 부분 일치(cb in pm)로 폴백.
    """
    pm = to_text(part_mat).upper()
    cb = to_text(class_base).upper()
    if not pm or not cb:
        return None

    m = allowlist if allowlist is not None else _load_base_material_allowlist()
    tokens = m.get(cb)
    if tokens is not None:
        if not tokens:
            return None
        if any(to_text(tok).upper() in pm for tok in tokens):
            return None
        return f"Material {pm!r} not in allowlist for Class_Base_Material {cb!r}"

    if cb in pm or pm in cb:
        return None
    return f"Material {pm!r} may not align with Class_Base_Material {cb!r}"


def matl_code_for_constraint(
    ws,
    row_idx: int,
    header_to_col: dict[str, int],
) -> str:
    return get_cell_text(ws, row_idx, header_to_col, "Matl_Code")


def corrosion_allowance_validation_messages_from_bundle(
    bundle,
) -> tuple[list[str], list[str]]:
    """Bundle 기반 corrosion_allowance 검증."""
    errors: list[str] = []
    warnings: list[str] = []

    unit_system = (bundle.global_settings.unit_system or "SI").strip() or "SI"
    ca_unit = "inch" if unit_system == "US Customary" else "mm"
    empty_policy = str(
        config.config_manager.get(
            "validation_policy.corrosion_allowance.empty_value_policy",
            "warning",
        )
        or "warning"
    ).strip().lower()

    for idx, row in enumerate(bundle.class_define_rows, start=1):
        class_name = (row.get("Class_Name") or "").strip()
        if not class_name:
            continue
        ca_raw = (row.get("Corrosion_Allowance") or "").strip()
        if not ca_raw:
            msg = (
                f"Class_Define row {idx} Class {class_name}: "
                f"Corrosion_Allowance is empty ({ca_unit})."
            )
            if empty_policy == "error":
                errors.append(msg)
            else:
                warnings.append(msg)
            continue
        try:
            float(ca_raw)
        except ValueError:
            errors.append(
                f"Class_Define row {idx} Class {class_name}: "
                f"Corrosion_Allowance must be numeric; got {ca_raw!r}."
            )
    return errors, warnings


def log_class_constraint_warnings_for_row(
    logger,
    sheet_name: str,
    class_name: str,
    row_idx: int,
    row: dict[str, str],
    class_specs: dict[str, ClassSpec],
) -> None:
    """log_class_constraint_warnings 의 dict-row 버전."""
    spec = class_specs.get(class_name)
    if not spec:
        return

    # Rating 비교 없음 — class 내 이종 rating/규격 component 는 정상 (연결부).

    class_base = spec.get("class_base_material", "")
    if sheet_name in VALVE_SHEET_NAMES:
        part_mat = to_text(row.get("Matl_Code") or "")
    elif sheet_name in (
        "Pipe_Group",
        "Forged_Fitting_Group",
        "Wrought_Fitting_Group",
        "Flange_Group",
    ):
        part_mat = _matl_code_for_constraint_dict(row)
    else:
        part_mat = ""

    mmsg = base_material_hint_message(part_mat, class_base, _load_base_material_allowlist())
    if mmsg:
        logger.warning(f"{sheet_name} row {row_idx} Class {class_name}: {mmsg}")


def _matl_code_for_constraint_dict(row: dict[str, str]) -> str:
    return to_text(row.get("Matl_Code") or "")


def _pick_first_non_empty_dict(row: dict[str, str], fields: list[str]) -> str:
    for f in fields:
        v = to_text(row.get(f) or "")
        if v:
            return v
    return ""


def log_class_constraint_warnings(
    logger,
    sheet_name: str,
    class_name: str,
    row_idx: int,
    ws,
    header_to_col: dict[str, int],
    class_specs: dict[str, ClassSpec],
) -> None:
    """ClassSpec 대비 Rating·재질 힌트를 로그에 남깁니다 (스킵 시 전체 실행은 계속)."""
    spec = class_specs.get(class_name)
    if not spec:
        return
    # Rating 비교 없음 — class 내 이종 rating/규격 component 는 정상 (연결부).

    class_base = spec.get("class_base_material", "")
    if sheet_name in VALVE_SHEET_NAMES:
        part_mat = get_cell_text(ws, row_idx, header_to_col, "Matl_Code")
    elif sheet_name in (
        "Pipe_Group",
        "Forged_Fitting_Group",
        "Wrought_Fitting_Group",
        "Flange_Group",
    ):
        part_mat = matl_code_for_constraint(ws, row_idx, header_to_col)
    else:
        part_mat = ""

    mmsg = base_material_hint_message(part_mat, class_base, _load_base_material_allowlist())
    if mmsg:
        logger.warning(f"{sheet_name} row {row_idx} Class {class_name}: {mmsg}")


def class_base_material_group_keys() -> list[str]:
    """
    Keys of ``base_material_allowlist`` in ``class_material_mapping.json``
    (e.g. KCS). These are the class-level material *group* tokens, not ASTM
    grade rows under each key.
    """
    return sorted(_load_base_material_allowlist().keys())


# (Class_Rating 콤보 옵션은 domain_schema.field_value_options("Class_Define",
#  "Class_Rating") 로 이동 — SSOT. rating 정합 검사도 폐지되어 관련 상수 없음.)
