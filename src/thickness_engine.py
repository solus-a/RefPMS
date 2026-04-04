"""
사이즈·클래스별 Schedule(두께) 룩업.

NPS 마스터는 project_config.json의 nps_list를 사용합니다.
행(파이프 등) **사이즈 전개**는 nps_list 연속 구간만 사용합니다.
**Schedule 룩업**은 우선 동일 규칙으로 매칭하고, 리스트에 없는 NPS라도
From~To **숫자 구간**에 들어가면 해당 Schedule을 씁니다(Reducing 등).
"""

from __future__ import annotations

import config

from excel_sheet_utils import (
    build_header_index,
    detect_header_row,
    get_cell_text,
    to_float,
    to_text,
)

cfg = config.config_manager

SCHEDULE_REQUIRED_HEADERS = [
    "Class_Name",
    "Size_From",
    "Size_To",
    "Schedule",
]


def nps_list() -> list[str]:
    return list(cfg.get("nps_master.nps_list", []) or [])


def explode_size_range(size_from: str, size_to: str) -> list[str]:
    master = nps_list()
    from_num = to_float(to_text(size_from))
    to_num = to_float(to_text(size_to))
    if from_num is None or to_num is None:
        return []

    nps_index_by_float = {float(nps): idx for idx, nps in enumerate(master)}
    from_idx = nps_index_by_float.get(from_num)
    to_idx = nps_index_by_float.get(to_num)
    if from_idx is None or to_idx is None:
        return []
    if from_idx > to_idx:
        return []

    return master[from_idx : to_idx + 1]


def load_schedule_rows(workbook) -> list[dict[str, str]]:
    if "Schedule" not in workbook.sheetnames:
        return []

    ws = workbook["Schedule"]
    try:
        header_row = detect_header_row(ws, SCHEDULE_REQUIRED_HEADERS)
    except ValueError:
        return []

    header_to_col = build_header_index(ws, header_row)
    missing = [h for h in SCHEDULE_REQUIRED_HEADERS if h not in header_to_col]
    if missing:
        return []

    rows: list[dict[str, str]] = []
    for row_idx in range(header_row + 1, ws.max_row + 1):
        class_name = get_cell_text(ws, row_idx, header_to_col, "Class_Name")
        if not class_name:
            continue
        rows.append(
            {
                "Class_Name": class_name,
                "Size_From": get_cell_text(ws, row_idx, header_to_col, "Size_From"),
                "Size_To": get_cell_text(ws, row_idx, header_to_col, "Size_To"),
                "Schedule": get_cell_text(ws, row_idx, header_to_col, "Schedule"),
            }
        )
    return rows


def lookup_schedule_thickness(
    schedule_rows: list[dict[str, str]],
    class_name: str,
    size_nps: str,
) -> str:
    if not size_nps or not class_name:
        return ""

    size_val = to_float(to_text(size_nps))

    for row in schedule_rows:
        if row["Class_Name"] != class_name:
            continue
        exploded = explode_size_range(row["Size_From"], row["Size_To"])
        if exploded and size_nps in exploded:
            return row["Schedule"]
        if not row["Size_To"] and row["Size_From"] and size_nps == row["Size_From"]:
            return row["Schedule"]
        if size_val is not None:
            lo = to_float(to_text(row["Size_From"]))
            hi = to_float(to_text(row["Size_To"]))
            if lo is not None:
                upper = hi if hi is not None else lo
                if lo <= size_val <= upper:
                    return row["Schedule"]

    return ""
