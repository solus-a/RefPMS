from __future__ import annotations

from typing import Literal

import config
from class_level_model import SizeTableRow

MIN_REDUCING_SIZE1_NPS = 0.75

BRANCH_ITEM_TYPES_OK = frozenset({"T", "RT", "TH"})
REDUCING_ITEM_TYPES_OK = frozenset({"RD", "SN"})


def size_number(size_text: str) -> float:
    return float(size_text.strip())


def normalize_nominal_mode(mode: str | None) -> Literal["NPS", "DN"]:
    """Class 별 nominal_size_system (NPS/DN) 를 정규화. 빈 값 또는 미지정 시 'NPS' 폴백."""
    s = str(mode or "").strip().upper()
    if s == "DN":
        return "DN"
    return "NPS"


def load_axis_allowlist(nominal_mode: str | None = None) -> frozenset[str]:
    """
    Size_Matrix 축에 허용되는 사이즈 집합.

    기본 기준은 **표준 카탈로그 전체 (ASME B36.10 / ISO 6708)**.  클래스별 Size Range
    (`Class_Size_Range` 시트)는 이 축 목록을 다시 좁히는 2차 게이트로 생성 파이프라인에서
    적용한다 (교차 시트 검증).
    """
    mode = normalize_nominal_mode(nominal_mode)
    return frozenset(config.catalog_sizes_all(mode))


def sorted_nominal_master_list(nominal_mode: str | None = None) -> list[str]:
    """Size_Matrix 축 기준 — 표준 카탈로그(전체 사이즈) 숫자 정렬."""
    mode = normalize_nominal_mode(nominal_mode)
    raw = config.catalog_sizes_all(mode)
    return sorted(set(raw), key=size_number)


def default_size1_rows(
    pair_kind: Literal["reducing", "branch"],
    nominal_mode: str | None = None,
) -> list[str]:
    allowed = load_axis_allowlist(nominal_mode)
    raw = sorted(set(allowed), key=size_number)
    if pair_kind == "reducing":
        raw = [x for x in raw if size_number(x) >= MIN_REDUCING_SIZE1_NPS]
    return raw


def default_size2_cols(
    pair_kind: Literal["reducing", "branch"],
    nominal_mode: str | None = None,
) -> list[str]:
    del pair_kind
    allowed = load_axis_allowlist(nominal_mode)
    return sorted(set(allowed), key=size_number)


def merge_axis(default_axis: list[str], extra: set[str], allowed: frozenset[str]) -> list[str]:
    merged = sorted(set(default_axis) | extra, key=size_number)
    if not allowed:
        return merged
    return [x for x in merged if x in allowed]


def cell_allowed(
    size1: str,
    size2: str,
    pair_kind: Literal["reducing", "branch"],
) -> bool:
    try:
        n1 = size_number(size1)
        n2 = size_number(size2)
    except (TypeError, ValueError):
        return False
    if pair_kind == "reducing":
        if n1 < MIN_REDUCING_SIZE1_NPS:
            return False
        return n2 < n1
    return n2 <= n1


def axes_from_rows(
    rows: list[SizeTableRow],
    pair_kind: Literal["reducing", "branch"],
    nominal_mode: str | None = None,
) -> tuple[list[str], list[str]]:
    allowed = load_axis_allowlist(nominal_mode)
    s1: set[str] = set()
    s2: set[str] = set()
    for r in rows:
        if r.size1.strip():
            s1.add(r.size1.strip())
        if r.size2.strip():
            s2.add(r.size2.strip())
    r1 = merge_axis(default_size1_rows(pair_kind, nominal_mode), s1, allowed)
    c2 = merge_axis(default_size2_cols(pair_kind, nominal_mode), s2, allowed)
    return r1, c2


def matrix_help_text(pair_kind: Literal["reducing", "branch"], nominal: str) -> str:
    common = (
        f"Nominal size mode: {nominal} (from the owning Class's Nominal_Size_System). "
        "Row/column headers are drawn from the built-in standard catalog "
        "(ASME B36.10 for NPS, ISO 6708 for DN). Per-Class Size Range narrows which of those "
        "are actually usable when the Piping_Material_Class_Data file is generated.\n\n"
        "Navigation (Excel-like): click selects a cell; drag a rectangle to replace the selection. "
        "Ctrl+drag adds a rectangle to the current selection. Shift+click or Shift+drag unions a rectangle "
        "from the anchor to the pointer with the existing selection (keeps prior Ctrl-added cells). "
        "Ctrl+click (no drag) toggles a single cell and moves the anchor there. "
        "Shift+arrows extend the rectangle from the anchor the same way (union). "
        "Arrow keys move the active cell; plain click or arrows replace the selection with a single cell. "
        "Selection and anchor always stay on editable (white) cells.\n"
        "F2 or typing starts edit. Arrow keys while editing commit the cell and move. "
        "Ctrl+Enter copies the active cell value into all selected cells. "
        "Ctrl+C / Ctrl+V copy and paste TSV blocks.\n\n"
        "Item_Type is stored in UPPERCASE.\n"
        "Edit Size opens a list (one row per nominal from the standard catalog): two checkboxes per row — "
        "whether that label is enabled on the Size1 axis (rows) and on the Size2 axis (columns). "
        "Unchecked axis greys the entire corresponding row or column in the matrix (geometry rules still apply).\n"
        "Reset clears every editable cell's Item_Type value; axis enable flags are unchanged.\n"
    )
    if pair_kind == "reducing":
        return (
            common
            + "Reducing table\n"
            + "-------------\n"
            + "Rows: Main Size (Size1). Columns: Reducing Size (Size2).\n"
            + "White cells exist only where Reducing Size < Main Size and Main Size ≥ 0.75 NPS.\n"
            + "Allowed Item_Type values: RD, SN (only). Empty cell is neutral.\n"
            + "Invalid (non-empty, not RD/SN) cells are shown with a red background.\n"
        )
    return (
        common
        + "Branch table\n"
        + "------------\n"
        + "Rows: Header size (Size1). Columns: Branch Size (Size2).\n"
        + "White cells exist where Branch Size ≤ Header size.\n"
        + "Allowed Item_Type values: T, RT, TH (only). Empty cell is neutral.\n"
        + "Invalid cells use a red background.\n"
    )
