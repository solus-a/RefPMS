"""체크리스트 2-3: GUI Item_Description 미리보기(_DESCRIPTION_SPECS) 출력 고정."""
from __future__ import annotations

import pytest

from class_template_wizard import _DESCRIPTION_SPECS, COMPONENT_GROUPS, _combined_component_name
from sample_data import component_rows

EXPECTED: dict[tuple[str, str], str] = {
    ("Pipe_Group", "P"): "PIPE A106-B SMLS PE",
    ("Pipe_Group", "JN"): "NIPPLE A106-B SMLS PE 50mm",
    ("Forged_Fitting_Group", "E"): "ELBOW 90 DEG A105 SW CL3000",
    ("Forged_Fitting_Group", "T"): "TEE A105 SW CL3000",
    ("Forged_Fitting_Group", "CP"): "CAP A105 SW CL3000",
    ("Forged_Fitting_Group", "JFR"): "REDUCING FULL COUPLING A105 SW CL3000",
    ("Forged_Fitting_Group", "JB"): "BUSHING A105 NPT CL3000",
    ("Wrought_Fitting_Group", "E"): "ELBOW 90 DEG LR A234-WPB SMLS BW",
    ("Wrought_Fitting_Group", "E4"): "ELBOW 45 DEG LR A234-WPB SMLS BW",
    ("Wrought_Fitting_Group", "T"): "TEE A234-WPB SMLS BW",
    ("Wrought_Fitting_Group", "CP"): "CAP A234-WPB SMLS BW",
    ("Flange_Group", "F"): "FLANGE A105 WN CL150 RF",
    ("Flange_Group", "FB"): "BLIND FLANGE A105 CL150 RF",
    ("Gasket_Group", "G"): "GASKET SHEET COMPRESSED NON-ASBESTOS ARAMID FIBER+NBR CL150 RF 1.5mm",
    ("Bolt_Group", "B"): "STUD BOLT A307-B / A194-2H HEX NUTS",
    ("Gate_Valve_Group", "VA"): "GATE VALVE A216-WCB / 13CR CL150 FLGD RF BB OS&Y HW",
    ("Globe_Valve_Group", "VB"): "GLOBE VALVE A216-WCB / 13CR CL150 FLGD RF BB OS&Y HW",
    ("Check_Valve_Group", "VC"): "CHECK VALVE A216-WCB / 13CR CL150 FLGD RF BC SWING",
    ("Ball_Valve_Group", "VL"): "BALL VALVE A216-WCB / SS316+PTFE CL150 FLGD RF FB HW",
    ("Butterfly_Valve_Group", "VU"): "BUTTERFLY VALVE A216-WCB / SS316+EPDM CL150 WAFER CONCENTRIC HW",
    ("Plug_Valve_Group", "VP"): "PLUG VALVE A216-WCB / SS316+PTFE CL150 FLGD RF LUBRICATED HW",
    ("Needle_Valve_Group", "VN"): "NEEDLE VALVE A105 / SS316+PTFE CL150 SW BB OS&Y HW",
}


_SAMPLE_CASES = [
    pytest.param(sheet, row, id=f"{sheet}-{row['Item_Code']}")
    for sheet, rows in component_rows().items()
    for row in rows
]


@pytest.mark.parametrize("sheet, row", _SAMPLE_CASES)
def test_preview_matches_golden(sheet, row):
    assert _combined_component_name(sheet, row) == EXPECTED[(sheet, row["Item_Code"])]


def test_every_component_group_has_a_spec():
    groups = {sheet for sheet, _label, _headers in COMPONENT_GROUPS}
    assert groups == set(_DESCRIPTION_SPECS)


def test_empty_tokens_are_skipped_with_their_separator():
    row = dict(component_rows()["Ball_Valve_Group"][0], Trim_Matl="", Seat_Matl="PTFE")
    # Trim 이 비면 " / " 는 사라지고 Seat 는 자기 구분자(+)로 Matl_Code 뒤에 붙는다.
    assert _combined_component_name("Ball_Valve_Group", row) == (
        "BALL VALVE A216-WCB+PTFE CL150 FLGD RF FB HW"
    )


def test_remarks_is_appended_last():
    row = dict(component_rows()["Pipe_Group"][0], Remarks="GALV")
    assert _combined_component_name("Pipe_Group", row) == "PIPE A106-B SMLS PE GALV"
