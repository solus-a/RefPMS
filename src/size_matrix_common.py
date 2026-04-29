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


