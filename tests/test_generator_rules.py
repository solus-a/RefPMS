"""생성기 규칙 단위 테스트 — 공용 샘플이 거치지 않는 경로."""
from __future__ import annotations

import pytest

from pms_generator import _forged_fitting_thickness, _item_code_entry


@pytest.mark.parametrize(
    "item_code, expected",
    [
        ("E", "CL3000"),    # B16.11 §2.1: Class 로 식별
        ("TH", "CL3000"),
        ("JFR", "CL3000"),
        ("JP", ""),         # B16.11: Plug·Bushing 은 class 로 식별하지 않음
        ("JB", ""),
        ("RCS", "SCH80"),   # MSS SP-95 Swage: Schedule 기준
        ("RES", "SCH80"),
    ],
)
def test_forged_fitting_thickness(item_code, expected):
    assert _forged_fitting_thickness(item_code, "CL3000", "SCH80") == expected


def test_item_code_lookup_is_scoped_by_sheet():
    # 같은 코드 E 가 그룹마다 다른 부품 — B16.11 단조 엘보에는 LR/SR 개념이 없다.
    assert _item_code_entry("Forged_Fitting_Group", "E")["code_name"] == "ELBOW 90 DEG"
    assert _item_code_entry("Wrought_Fitting_Group", "E")["code_name"] == "ELBOW 90 DEG LR"
    assert _item_code_entry("Wrought_Fitting_Group", "ES")["code_name"] == "ELBOW 90 DEG SR"


def test_item_code_lookup_misses_return_empty():
    assert _item_code_entry("Pipe_Group", "VA") == {}
