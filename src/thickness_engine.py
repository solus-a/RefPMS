"""
사이즈·클래스별 Schedule(두께) 룩업.

명목지름(NPS/DN)은 **클래스 단위** 로 주입해야 한다. Class_Define
의 ``Nominal_Size_System`` 값을 호출부가 모아서 ``nominal_mode`` 로 전달하면
해당 **표준 카탈로그** (ASME B36.10 NPS 또는 ISO 6708 DN) 전체를 master 로
사용한다. 클래스별로 실제 활성 사이즈 부분집합(`Class_Size_Range`) 은
상위 파이프라인이 적용한다.
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

SCHEDULE_REQUIRED_HEADERS = [
    "Class_Name",
    "Size_From",
    "Size_To",
    "Schedule",
]


def nps_list() -> list[str]:
    """표준 카탈로그(ASME B36.10) NPS 전체 목록."""
    return list(config.catalog_nps_all())


def dn_list() -> list[str]:
    """표준 카탈로그(ISO 6708) DN 전체 목록."""
    return list(config.catalog_dn_all())


def nominal_size_master(nominal_mode: str) -> list[str]:
    """
    클래스의 Nominal_Size_System 값에 따라 표준 카탈로그를 반환.
    DN → DN 카탈로그, NPS(또는 미설정) → NPS 카탈로그.
    """
    raw = str(nominal_mode or "").strip().upper()
    return list(config.catalog_sizes_all(raw))


def explode_size_range(size_from: str, size_to: str, nominal_mode: str) -> list[str]:
    master = nominal_size_master(nominal_mode)
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


def load_schedule_rows_from_bundle(bundle) -> list[dict[str, str]]:
    """ClassLevelBundle.schedule_rows 에서 기존 workbook loader 와 동일 형태의 list 를 만듦.

    빈 Class_Name row 는 제외. 키는 ``Class_Name / Size_From / Size_To / Schedule``.
    """
    rows: list[dict[str, str]] = []
    for row in bundle.schedule_rows:
        class_name = str(row.get("Class_Name") or "").strip()
        if not class_name:
            continue
        rows.append(
            {
                "Class_Name": class_name,
                "Size_From": str(row.get("Size_From") or ""),
                "Size_To": str(row.get("Size_To") or ""),
                "Schedule": str(row.get("Schedule") or ""),
            }
        )
    return rows


def lookup_schedule_thickness(
    schedule_rows: list[dict[str, str]],
    class_name: str,
    size_nps: str,
    nominal_mode: str,
) -> str:
    if not size_nps or not class_name:
        return ""

    size_val = to_float(to_text(size_nps))

    for row in schedule_rows:
        if row["Class_Name"] != class_name:
            continue
        exploded = explode_size_range(row["Size_From"], row["Size_To"], nominal_mode)
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
