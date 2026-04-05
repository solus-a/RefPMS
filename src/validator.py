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
