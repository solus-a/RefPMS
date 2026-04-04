"""엑셀 시트 헤더·셀 읽기 공통 유틸 (openpyxl 워크시트용)."""

from __future__ import annotations

from typing import Optional


def to_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def to_float(text_value: str) -> Optional[float]:
    if not text_value:
        return None
    try:
        return float(text_value)
    except ValueError:
        return None


def detect_header_row(ws, expected_headers: list[str], max_scan_rows: int = 10) -> int:
    for row_idx in range(1, max_scan_rows + 1):
        row_values = [ws.cell(row=row_idx, column=c).value for c in range(1, ws.max_column + 1)]
        header_set = {to_text(v) for v in row_values if to_text(v)}
        if all(h in header_set for h in expected_headers):
            return row_idx
    raise ValueError(
        f"Could not detect header row in sheet '{ws.title}'. "
        f"Expected headers: {', '.join(expected_headers)}"
    )


def build_header_index(ws, header_row: int) -> dict[str, int]:
    header_to_col: dict[str, int] = {}
    for col in range(1, ws.max_column + 1):
        header = to_text(ws.cell(row=header_row, column=col).value)
        if header:
            header_to_col[header] = col
    return header_to_col


def get_cell_text(ws, row_idx: int, header_to_col: dict[str, int], header_name: Optional[str]) -> str:
    if not header_name:
        return ""
    col = header_to_col.get(header_name)
    if not col:
        return ""
    return to_text(ws.cell(row=row_idx, column=col).value)


def pick_first_non_empty(
    ws,
    row_idx: int,
    header_to_col: dict[str, int],
    candidates: list[str],
) -> str:
    for name in candidates:
        value = get_cell_text(ws, row_idx, header_to_col, name)
        if value:
            return value
    return ""
