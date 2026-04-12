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

CLASS_DEFINE_REQUIRED_HEADERS = ["Class_Name"]

# 엑셀 열 이름 → ClassSpec 키
_EXCEL_TO_SPEC_KEY: dict[str, str] = {
    "Class_Name": "class_name",
    "Revision_No": "revision_no",
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


class ClassSpec(TypedDict, total=False):
    class_name: str
    revision_no: str
    design_code: str
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


# ASME B16.5 플랜지 P-T Class (Class_Rating과 동계열)
_B16_5_PRESSURE_CLASSES = frozenset({150, 300, 400, 600, 900, 1500, 2500})
# ASME B16.11 단조 이음관 등급 (소켓·나사, 3000#·CL3000 등)
_B16_11_FORGED_RATING_CLASSES = frozenset({2000, 3000, 6000, 9000})

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
    out: dict[str, ClassSpec] = {}

    for row_idx in range(header_row + 1, ws.max_row + 1):
        name = get_cell_text(ws, row_idx, header_to_col, "Class_Name")
        if not name:
            continue
        spec: ClassSpec = {"class_name": name}
        for excel_header, key in _EXCEL_TO_SPEC_KEY.items():
            if excel_header == "Class_Name":
                continue
            if excel_header not in header_to_col:
                continue
            val = get_cell_text(ws, row_idx, header_to_col, excel_header)
            if val:
                spec[key] = val  # type: ignore[literal-required]
        out[name] = spec

    return out


def _normalize_rating_token(raw: str) -> str:
    t = to_text(raw).upper().replace(" ", "")
    if t.startswith("CL"):
        t = t[2:]
    if t.endswith("#"):
        t = t[:-1]
    return t


def _rating_class_number(raw: str) -> Optional[int]:
    """숫자만 있는 Class(150, 3000 등) 파싱. PN 등은 None."""
    t = _normalize_rating_token(raw)
    if t.isdigit():
        return int(t)
    return None


def rating_mismatch_message(row_rating: str, class_rating: str) -> Optional[str]:
    """
    행 Rating vs Class_Define Class_Rating.
    동일 규격 체계에서만 '불일치'로 본다.
    - Class_Rating은 보통 ASME B16.5 플랜지 P-T Class(150, 300, …).
    - CL3000·3000# 등은 ASME B16.11 단조 이음관 등급이므로 B16.5 Class와 직접 비교하지 않음.
    """
    rr = to_text(row_rating)
    cr = to_text(class_rating)
    if not rr or not cr:
        return None
    if _normalize_rating_token(rr) == _normalize_rating_token(cr):
        return None

    rn = _rating_class_number(rr)
    cn = _rating_class_number(cr)
    if rn is not None and cn is not None:
        r_b5 = rn in _B16_5_PRESSURE_CLASSES
        r_b11 = rn in _B16_11_FORGED_RATING_CLASSES
        c_b5 = cn in _B16_5_PRESSURE_CLASSES
        c_b11 = cn in _B16_11_FORGED_RATING_CLASSES
        if (r_b5 and c_b11) or (r_b11 and c_b5):
            return None
        if r_b5 and c_b5 and rn != cn:
            return f"Rating {rr!r} does not match class Class_Rating {cr!r}"
        if r_b11 and c_b11 and rn != cn:
            return f"Rating {rr!r} does not match class Class_Rating {cr!r}"

    return f"Rating {rr!r} does not match class Class_Rating {cr!r}"


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


def row_rating_for_constraint_check(
    sheet_name: str,
    ws,
    row_idx: int,
    header_to_col: dict[str, int],
) -> str:
    """부품 시트에서 클래스 등급 대비 검사에 쓸 Rating 문자열."""
    if sheet_name == "Flange_Group":
        return pick_first_non_empty(ws, row_idx, header_to_col, ["Rating", "Rating_Thickness"])
    if sheet_name in ("Valve", "Valve_Group"):
        return pick_first_non_empty(ws, row_idx, header_to_col, ["Rating", "Rating_Thickness"])
    if sheet_name == "Fitting_Group":
        return get_cell_text(ws, row_idx, header_to_col, "Rating")
    return ""


def mat_code_grade_for_constraint(
    ws,
    row_idx: int,
    header_to_col: dict[str, int],
) -> str:
    mat_code = get_cell_text(ws, row_idx, header_to_col, "Mat_Code")
    mat_grade = pick_first_non_empty(
        ws,
        row_idx,
        header_to_col,
        ["Mat_Grade", "Material_Code_Grade", "Mat_Class"],
    )
    if mat_code and mat_grade:
        return f"{mat_code}-{mat_grade}"
    return mat_code or mat_grade


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
    class_rating = spec.get("class_rating", "")
    row_rating = row_rating_for_constraint_check(sheet_name, ws, row_idx, header_to_col)
    rmsg = rating_mismatch_message(row_rating, class_rating)
    if rmsg:
        logger.warning(f"{sheet_name} row {row_idx} Class {class_name}: {rmsg}")

    class_base = spec.get("class_base_material", "")
    if sheet_name in ("Valve", "Valve_Group"):
        part_mat = get_cell_text(ws, row_idx, header_to_col, "Body_Mat")
    elif sheet_name in ("Pipe_Group", "Fitting_Group", "Flange_Group"):
        part_mat = mat_code_grade_for_constraint(ws, row_idx, header_to_col)
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


def flange_pt_class_rating_options() -> list[str]:
    """ASME B16.5 flange pressure–temperature class numbers as strings (150, 300, …)."""
    return [str(x) for x in sorted(_B16_5_PRESSURE_CLASSES)]
