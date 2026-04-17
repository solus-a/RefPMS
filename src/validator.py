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


def validate_template_row(
    sheet_name: str,
    ws,
    row_idx: int,
    header_to_col: dict[str, int],
    mapping: dict[str, Any],
) -> list[str]:
    """
    단일 데이터 행에 대한 검증 메시지 목록 (비어 있으면 통과).
    규칙은 시트에 실제 존재하는 헤더에만 적용한다.
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

    return messages


# ---------------------------------------------------------------------------
# Cross-sheet Class Size Range validation
# ---------------------------------------------------------------------------

def load_class_size_ranges(workbook) -> dict[str, list[str]]:
    """템플릿 workbook 에서 Class_Size_Range 시트를 읽어 Class_Name → active sizes.

    시트가 없거나 비어 있으면 빈 dict. 호출 측에서 빈 dict ⇒ "범위 미선언" 으로 간주하여
    해당 검증을 건너뛸 수 있습니다.
    """
    if workbook is None or "Class_Size_Range" not in workbook.sheetnames:
        return {}
    ws = workbook["Class_Size_Range"]
    from excel_sheet_utils import (
        build_header_index as _bhi,
        detect_header_row as _dhr,
        to_text as _tt,
    )
    headers = ["Class_Name", "Active_Sizes"]
    try:
        hr = _dhr(ws, headers)
    except ValueError:
        return {}
    htc = _bhi(ws, hr)
    if any(h not in htc for h in headers):
        return {}
    out: dict[str, list[str]] = {}
    for r in range(hr + 1, ws.max_row + 1):
        name = _tt(ws.cell(row=r, column=htc["Class_Name"]).value).strip()
        if not name:
            continue
        raw = _tt(ws.cell(row=r, column=htc["Active_Sizes"]).value)
        sizes: list[str] = []
        if raw:
            for token in str(raw).replace(";", ",").replace(" ", ",").split(","):
                t = token.strip()
                if t:
                    sizes.append(t)
        out[name] = sizes
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
                f"Size Range (declared in Class_Size_Range sheet)."
            )
    return messages
