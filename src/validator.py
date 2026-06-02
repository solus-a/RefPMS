"""부품군별 템플릿 행 검증 (component_mapping.json 기반)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import config
from excel_sheet_utils import get_cell_text as _get_cell_text


def load_component_mapping(path: Path | None = None) -> dict[str, Any]:
    """
    data/component_mapping.json 로드.
    파일이 없거나 오류 시 빈 rules로 진행할 수 있게 최소 dict 반환.
    """
    p = path if path is not None else config.component_mapping_path()
    if not p.exists():
        return {"version": 0, "sheets": {}}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"version": 0, "sheets": {}}
        if "sheets" not in data or not isinstance(data["sheets"], dict):
            data["sheets"] = {}
        return data
    except (OSError, json.JSONDecodeError):
        return {"version": 0, "sheets": {}}


def load_matl_code_category_lookup(
    path: Path | None = None,
) -> dict[str, dict[str, str]]:
    """data/field_values.json 의 Matl_Code 옵션 → category 룩업 테이블 빌드.

    반환 구조: ``{sheet_name: {matl_code_short: category}}``. 시트나 Matl_Code
    옵션이 없으면 해당 키 누락. ``code_category_consistency`` rule 이 이 룩업을
    사용한다.
    """
    p = path if path is not None else config.field_values_db_path()
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for sheet_name, sheet in data.items():
        if sheet_name.startswith("_") or not isinstance(sheet, dict):
            continue
        options = sheet.get("Matl_Code")
        if not isinstance(options, list):
            continue
        sheet_lookup: dict[str, str] = {}
        for item in options:
            if not isinstance(item, dict):
                continue
            short = str(item.get("short", "")).strip()
            category = str(item.get("category", "")).strip()
            if short and category:
                sheet_lookup[short] = category
        if sheet_lookup:
            out[sheet_name] = sheet_lookup
    return out


def validate_template_row(
    sheet_name: str,
    ws,
    row_idx: int,
    header_to_col: dict[str, int],
    mapping: dict[str, Any],
    matl_code_categories: dict[str, dict[str, str]] | None = None,
) -> list[str]:
    """
    단일 데이터 행에 대한 검증 메시지 목록 (비어 있으면 통과).
    규칙은 시트에 실제 존재하는 헤더에만 적용한다.

    ``matl_code_categories`` 는 ``load_matl_code_category_lookup`` 결과로,
    ``code_category_consistency`` rule 처리 시 코드→카테고리 조회에 사용.
    """
    sheets = mapping.get("sheets") or {}
    rules = sheets.get(sheet_name)
    if not rules or not isinstance(rules, dict):
        return []

    messages: list[str] = []

    for field in rules.get("required_non_empty", []):
        if field not in header_to_col:
            continue
        if not _get_cell_text(ws, row_idx, header_to_col, field):
            messages.append(
                f"{sheet_name} row {row_idx}: required field empty: {field!r}"
            )

    for group in rules.get("xor_at_most_one_filled", []):
        if not isinstance(group, list) or len(group) < 2:
            continue
        filled = [
            f
            for f in group
            if f in header_to_col and _get_cell_text(ws, row_idx, header_to_col, f)
        ]
        if len(filled) >= 2:
            messages.append(
                f"{sheet_name} row {row_idx}: at most one of {group!r} may be filled; got: {filled!r}"
            )

    for cond in rules.get("conditional_required", []):
        if not isinstance(cond, dict):
            continue
        when_field = cond.get("when_field")
        if not when_field or when_field not in header_to_col:
            continue
        when_raw = _get_cell_text(ws, row_idx, header_to_col, when_field)
        when_values = cond.get("when_values") or []
        if not isinstance(when_values, list):
            continue
        allowed = {str(v).strip().upper() for v in when_values}
        if allowed and when_raw.strip().upper() not in allowed:
            continue
        for req in cond.get("require_non_empty", []):
            if req not in header_to_col:
                continue
            if not _get_cell_text(ws, row_idx, header_to_col, req):
                messages.append(
                    f"{sheet_name} row {row_idx}: when {when_field}={when_raw!r}, "
                    f"field {req!r} is required"
                )

    for cond in rules.get("conditional_empty", []):
        if not isinstance(cond, dict):
            continue
        when_field = cond.get("when_field")
        if not when_field or when_field not in header_to_col:
            continue
        when_raw = _get_cell_text(ws, row_idx, header_to_col, when_field)
        when_values = cond.get("when_values") or []
        if not isinstance(when_values, list):
            continue
        allowed = {str(v).strip().upper() for v in when_values}
        if allowed and when_raw.strip().upper() not in allowed:
            continue
        for req in cond.get("require_empty", []):
            if req not in header_to_col:
                continue
            value = _get_cell_text(ws, row_idx, header_to_col, req)
            if value:
                messages.append(
                    f"{sheet_name} row {row_idx}: when {when_field}={when_raw!r}, "
                    f"field {req!r} must be empty (got {value!r})"
                )

    sheet_lookup = (matl_code_categories or {}).get(sheet_name) or {}
    for rule in rules.get("code_category_consistency", []):
        if not isinstance(rule, dict):
            continue
        code_field = rule.get("code_field")
        category_field = rule.get("category_field")
        if not code_field or not category_field:
            continue
        if code_field not in header_to_col or category_field not in header_to_col:
            continue
        code_val = _get_cell_text(ws, row_idx, header_to_col, code_field).strip()
        category_val = _get_cell_text(ws, row_idx, header_to_col, category_field).strip()
        if not code_val or not category_val:
            continue
        expected = sheet_lookup.get(code_val)
        if expected is None:
            continue
        if expected != category_val:
            messages.append(
                f"{sheet_name} row {row_idx}: {code_field}={code_val!r} belongs to "
                f"category {expected!r}, but {category_field}={category_val!r}"
            )

    return messages


# ---------------------------------------------------------------------------
# Cross-sheet Class Size Range validation
# ---------------------------------------------------------------------------

def validate_class_define_uniqueness(workbook) -> list[str]:
    """Class_Define 시트의 Class_Name 컬럼 중복 검사.

    Class_Define.Class_Name 은 PK 역할 — 다른 시트가 FK 로 참조하므로 중복이
    있으면 cross-sheet 조회 결과가 비결정적이 된다. 중복 발견 시 사용자에게
    행 번호와 함께 보고한다. 시트가 없거나 Class_Name 컬럼이 없으면 빈 목록.
    """
    if workbook is None or "Class_Define" not in workbook.sheetnames:
        return []
    from excel_sheet_utils import (
        build_header_index as _bhi,
        detect_header_row as _dhr,
        to_text as _tt,
    )

    ws = workbook["Class_Define"]
    try:
        hr = _dhr(ws, ["Class_Name"])
    except ValueError:
        return []
    htc = _bhi(ws, hr)
    if "Class_Name" not in htc:
        return []

    first_seen: dict[str, int] = {}
    messages: list[str] = []
    for r in range(hr + 1, ws.max_row + 1):
        name = _tt(ws.cell(row=r, column=htc["Class_Name"]).value).strip()
        if not name:
            continue
        if name in first_seen:
            messages.append(
                f"Class_Define row {r}: duplicate Class_Name {name!r} "
                f"(also at row {first_seen[name]})"
            )
        else:
            first_seen[name] = r
    return messages


def load_class_size_ranges(workbook) -> dict[str, list[str]]:
    """템플릿 workbook 에서 Class_Define 시트의 Size_From / Size_To 와 Size_Selection 시트를 결합해
    Class_Name → active sizes 목록을 만든다.

    Class_Define 시트가 없거나 행이 비어 있으면 빈 dict.  Active sizes = (Class 의 Nominal_Size_System 에
    해당하는 Size_Selection) ∩ [Size_From, Size_To]  (양 끝 포함).
    """
    if workbook is None or "Class_Define" not in workbook.sheetnames:
        return {}
    from class_level_model import (
        _resolve_active_sizes,
        read_size_selection_from_workbook,
        default_size_selection_from_catalog,
    )
    from excel_sheet_utils import (
        build_header_index as _bhi,
        detect_header_row as _dhr,
        to_text as _tt,
    )

    selection = read_size_selection_from_workbook(workbook) or default_size_selection_from_catalog()

    ws = workbook["Class_Define"]
    required = ["Class_Name"]
    try:
        hr = _dhr(ws, required)
    except ValueError:
        return {}
    htc = _bhi(ws, hr)
    if "Class_Name" not in htc:
        return {}
    out: dict[str, list[str]] = {}
    for r in range(hr + 1, ws.max_row + 1):
        name = _tt(ws.cell(row=r, column=htc["Class_Name"]).value).strip()
        if not name:
            continue
        mode = ""
        if "Nominal_Size_System" in htc:
            mode = _tt(ws.cell(row=r, column=htc["Nominal_Size_System"]).value).strip()
        sf = _tt(ws.cell(row=r, column=htc["Size_From"]).value).strip() if "Size_From" in htc else ""
        st = _tt(ws.cell(row=r, column=htc["Size_To"]).value).strip() if "Size_To" in htc else ""
        out[name] = _resolve_active_sizes(selection, mode or "NPS", sf, st)
    return out


def validate_size_range_for_row(
    sheet_name: str,
    row_idx: int,
    class_name: str,
    ws,
    header_to_col: dict[str, int],
    size_from_field: str | None,
    size_to_field: str | None,
    class_size_ranges: dict[str, list[str]],
    size_label: str = "Size",
) -> list[str]:
    """Size_From/Size_To 가 해당 Class 의 Active Size Range 안에 있는지 확인.

    Class 의 Size Range 엔트리 자체가 없으면(= 선언 안 됨) 검증을 건너뜁니다.
    엔트리는 있지만 Size 값이 그 집합에 없으면 **에러** 메시지를 반환.
    """
    if not class_name or not class_size_ranges:
        return []
    active = class_size_ranges.get(class_name)
    if active is None:
        return []
    active_set = {str(s).strip() for s in active if str(s).strip()}
    if not active_set:
        return []
    messages: list[str] = []
    for field_name, role in (
        (size_from_field, f"{size_label} (From)"),
        (size_to_field, f"{size_label} (To)"),
    ):
        if not field_name or field_name not in header_to_col:
            continue
        val = _get_cell_text(ws, row_idx, header_to_col, field_name).strip()
        if not val:
            continue
        if val not in active_set:
            messages.append(
                f"{sheet_name} row {row_idx}: {role} {val!r} is outside Class {class_name!r} "
                f"Size Range (Class_Define Size_From/Size_To ∩ Size_Selection)."
            )
    return messages


# ---------------------------------------------------------------------------
# Bundle-based equivalents (no Workbook dependency)
# ---------------------------------------------------------------------------

def class_size_ranges_from_bundle(bundle) -> dict[str, list[str]]:
    """ClassLevelBundle 에서 Class_Name → active sizes 목록을 만든다."""
    out: dict[str, list[str]] = {}
    for row in bundle.class_define_rows:
        name = (row.get("Class_Name") or "").strip()
        if not name:
            continue
        out[name] = bundle.active_sizes_for_class(name)
    return out


def validate_template_row_dict(
    sheet_name: str,
    row_idx: int,
    row: dict[str, str],
    mapping: dict[str, Any],
    matl_code_categories: dict[str, dict[str, str]] | None = None,
) -> list[str]:
    """Workbook 의존 없는 dict-row 버전. row_idx 는 메시지에만 사용."""
    sheets = mapping.get("sheets") or {}
    rules = sheets.get(sheet_name)
    if not rules or not isinstance(rules, dict):
        return []

    def _v(field: str) -> str:
        return str(row.get(field, "") or "")

    messages: list[str] = []

    for field in rules.get("required_non_empty", []):
        if field not in row:
            continue
        if not _v(field):
            messages.append(
                f"{sheet_name} row {row_idx}: required field empty: {field!r}"
            )

    for group in rules.get("xor_at_most_one_filled", []):
        if not isinstance(group, list) or len(group) < 2:
            continue
        filled = [f for f in group if f in row and _v(f)]
        if len(filled) >= 2:
            messages.append(
                f"{sheet_name} row {row_idx}: at most one of {group!r} may be filled; got: {filled!r}"
            )

    for cond in rules.get("conditional_required", []):
        if not isinstance(cond, dict):
            continue
        when_field = cond.get("when_field")
        if not when_field or when_field not in row:
            continue
        when_raw = _v(when_field)
        when_values = cond.get("when_values") or []
        if not isinstance(when_values, list):
            continue
        allowed = {str(v).strip().upper() for v in when_values}
        if allowed and when_raw.strip().upper() not in allowed:
            continue
        for req in cond.get("require_non_empty", []):
            if req not in row:
                continue
            if not _v(req):
                messages.append(
                    f"{sheet_name} row {row_idx}: when {when_field}={when_raw!r}, "
                    f"field {req!r} is required"
                )

    for cond in rules.get("conditional_empty", []):
        if not isinstance(cond, dict):
            continue
        when_field = cond.get("when_field")
        if not when_field or when_field not in row:
            continue
        when_raw = _v(when_field)
        when_values = cond.get("when_values") or []
        if not isinstance(when_values, list):
            continue
        allowed = {str(v).strip().upper() for v in when_values}
        if allowed and when_raw.strip().upper() not in allowed:
            continue
        for req in cond.get("require_empty", []):
            if req not in row:
                continue
            value = _v(req)
            if value:
                messages.append(
                    f"{sheet_name} row {row_idx}: when {when_field}={when_raw!r}, "
                    f"field {req!r} must be empty (got {value!r})"
                )

    sheet_lookup = (matl_code_categories or {}).get(sheet_name) or {}
    for rule in rules.get("code_category_consistency", []):
        if not isinstance(rule, dict):
            continue
        code_field = rule.get("code_field")
        category_field = rule.get("category_field")
        if not code_field or not category_field:
            continue
        if code_field not in row or category_field not in row:
            continue
        code_val = _v(code_field).strip()
        category_val = _v(category_field).strip()
        if not code_val or not category_val:
            continue
        expected = sheet_lookup.get(code_val)
        if expected is None:
            continue
        if expected != category_val:
            messages.append(
                f"{sheet_name} row {row_idx}: {code_field}={code_val!r} belongs to "
                f"category {expected!r}, but {category_field}={category_val!r}"
            )

    return messages


def validate_size_range_for_row_dict(
    sheet_name: str,
    row_idx: int,
    class_name: str,
    row: dict[str, str],
    size_from_field: str | None,
    size_to_field: str | None,
    class_size_ranges: dict[str, list[str]],
    size_label: str = "Size",
) -> list[str]:
    """validate_size_range_for_row 의 dict-row 버전."""
    if not class_name or not class_size_ranges:
        return []
    active = class_size_ranges.get(class_name)
    if active is None:
        return []
    active_set = {str(s).strip() for s in active if str(s).strip()}
    if not active_set:
        return []
    messages: list[str] = []
    for field_name, role in (
        (size_from_field, f"{size_label} (From)"),
        (size_to_field, f"{size_label} (To)"),
    ):
        if not field_name:
            continue
        val = str(row.get(field_name, "") or "").strip()
        if not val:
            continue
        if val not in active_set:
            messages.append(
                f"{sheet_name} row {row_idx}: {role} {val!r} is outside Class {class_name!r} "
                f"Size Range (Class_Define Size_From/Size_To ∩ Size_Selection)."
            )
    return messages
