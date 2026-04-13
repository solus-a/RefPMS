from __future__ import annotations

from typing import Literal

import config
from class_level_model import SizeTableRow

MIN_REDUCING_SIZE1_NPS = 0.75

BRANCH_ITEM_TYPES_OK = frozenset({"T", "RT", "TH"})
REDUCING_ITEM_TYPES_OK = frozenset({"RD", "SN"})


def size_number(size_text: str) -> float:
    return float(size_text.strip())


def nominal_size_mode() -> Literal["NPS", "DN"]:
    raw = config.config_manager.get("units_notation.nominal_size.selected", "NPS")
    s = str(raw or "").strip().upper()
    if s == "DN":
        return "DN"
    return "NPS"


def load_axis_allowlist() -> frozenset[str]:
    mode = nominal_size_mode()
    key = "nps_master.dn_list" if mode == "DN" else "nps_master.nps_list"
    lst = config.config_manager.get(key, []) or []
    out: set[str] = set()
    if isinstance(lst, list):
        for x in lst:
            t = str(x).strip()
            if t:
                out.add(t)
    return frozenset(out)


def sorted_nominal_master_list() -> list[str]:
    """nps_master 순서(숫자 정렬) — Edit Size 대화상자 행과 매트릭스 축의 기준."""
    mode = nominal_size_mode()
    key = "nps_master.dn_list" if mode == "DN" else "nps_master.nps_list"
    lst = config.config_manager.get(key, []) or []
    if not isinstance(lst, list):
        return []
    raw = [str(x).strip() for x in lst if str(x).strip()]
    return sorted(set(raw), key=size_number)


def default_size1_rows(pair_kind: Literal["reducing", "branch"]) -> list[str]:
    allowed = load_axis_allowlist()
    raw = sorted(set(allowed), key=size_number)
    if pair_kind == "reducing":
        raw = [x for x in raw if size_number(x) >= MIN_REDUCING_SIZE1_NPS]
    return raw


def default_size2_cols(pair_kind: Literal["reducing", "branch"]) -> list[str]:
    del pair_kind
    allowed = load_axis_allowlist()
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
) -> tuple[list[str], list[str]]:
    allowed = load_axis_allowlist()
    s1: set[str] = set()
    s2: set[str] = set()
    for r in rows:
        if r.size1.strip():
            s1.add(r.size1.strip())
        if r.size2.strip():
            s2.add(r.size2.strip())
    r1 = merge_axis(default_size1_rows(pair_kind), s1, allowed)
    c2 = merge_axis(default_size2_cols(pair_kind), s2, allowed)
    return r1, c2


def matrix_help_text(pair_kind: Literal["reducing", "branch"], nominal: str) -> str:
    common = (
        f"Nominal size mode: {nominal} (from units_notation.nominal_size). "
        "Only sizes listed in nps_master for that mode may be used as row/column headers.\n\n"
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
        "Edit Size opens a list (one row per nominal from nps_master): two checkboxes per row — "
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
