"""규칙 변경 뒤의 경계 동작 — 불러오기 정규화와 PMS 엔진의 Constraint 적용."""
from __future__ import annotations

import copy

import pytest

from openpyxl import load_workbook

from pms_generator import generate_piping_material_class_data
from project_codec import bundle_from_json_dict, bundle_to_json_dict
from sample_data import build_sample_bundle, component_rows
from template_generator import generate_class_define_template, load_class_level_bundle_from_template


def _legacy_blind_flange() -> dict[str, str]:
    # Flange_Type 이 필수였던 시절에 저장된 FB 행 — 'WN' 이 남아 있다.
    fb = next(r for r in component_rows()["Flange_Group"] if r["Item_Code"] == "FB")
    return dict(fb, Flange_Type="WN")


def _bundle_with_legacy_blind():
    bundle = build_sample_bundle()
    bundle.component_rows["Flange_Group"] = [
        r for r in bundle.component_rows["Flange_Group"] if r["Item_Code"] != "FB"
    ] + [_legacy_blind_flange()]
    return bundle


def test_project_load_clears_fields_that_must_be_empty():
    data = bundle_to_json_dict(_bundle_with_legacy_blind())
    loaded = bundle_from_json_dict(copy.deepcopy(data))
    fb = next(r for r in loaded.component_rows["Flange_Group"] if r["Item_Code"] == "FB")
    assert fb["Flange_Type"] == ""
    f = next(r for r in loaded.component_rows["Flange_Group"] if r["Item_Code"] == "F")
    assert f["Flange_Type"] == "WN"  # F 는 그대로


def test_template_load_clears_fields_that_must_be_empty(tmp_path):
    path = generate_class_define_template(
        output_path=tmp_path / "t.xlsx", class_level=_bundle_with_legacy_blind()
    )
    loaded = load_class_level_bundle_from_template(path)
    fb = next(r for r in loaded.component_rows["Flange_Group"] if r["Item_Code"] == "FB")
    assert fb["Flange_Type"] == ""


def _generate(bundle, tmp_path) -> list[dict]:
    tpl = generate_class_define_template(output_path=tmp_path / "t.xlsx", class_level=bundle)
    out = generate_piping_material_class_data(tpl, output_path=tmp_path / "o.xlsx")
    values = list(load_workbook(out, read_only=True).worksheets[0].iter_rows(values_only=True))
    return [dict(zip(values[0], v)) for v in values[1:]]


def test_engine_drops_forged_row_violating_b16_11(tmp_path):
    # ASME B16.11 §2.1: SW 에 CL2000 은 없다 → 엔진이 그 행을 산출물에서 뺀다.
    bundle = build_sample_bundle()
    forged = bundle.component_rows["Forged_Fitting_Group"]
    bad = dict(forged[0], Item_Code="JF", End_Type="SW", Rating="CL2000")
    bundle.component_rows["Forged_Fitting_Group"] = forged + [bad]
    codes = {r["Item_Code"] for r in _generate(bundle, tmp_path)}
    assert "JF" not in codes
    assert "E" in codes  # 규칙에 맞는 단조 행은 그대로


@pytest.mark.parametrize("flange_type", ["SO", "LJ", "THRD", "so"])
def test_non_bore_matched_flange_has_no_schedule(tmp_path, flange_type):
    # SO·LJ 는 배관 외경에 끼우는 형식 (ASME B16.5 §7.7.1), THRD 는 나사 — Schedule 과 무관.
    bundle = build_sample_bundle()
    bundle.component_rows["Flange_Group"] = [
        dict(r, Flange_Type=flange_type) if r["Item_Code"] == "F" else r
        for r in bundle.component_rows["Flange_Group"]
    ]
    rows = [r for r in _generate(bundle, tmp_path) if r["Item_Code"] == "F"]
    assert rows
    assert {r["Thickness1"] for r in rows} == {None}
    assert all("SCH" not in r["Item_Description"] and "STD" not in r["Item_Description"] for r in rows)


def test_reducing_slip_on_flange_blanks_both_thicknesses(tmp_path):
    # FR 은 Size2 두께(Thickness2)도 계산되는데, SO 면 둘 다 비어야 한다.
    bundle = build_sample_bundle()
    f = next(r for r in bundle.component_rows["Flange_Group"] if r["Item_Code"] == "F")
    fr = dict(f, Item_Code="FR", Flange_Type="SO", Size1_From="2", Size1_To="4",
              Size2_From="1", Size2_To="1.5")
    bundle.component_rows["Flange_Group"].append(fr)
    rows = [r for r in _generate(bundle, tmp_path) if r["Item_Code"] == "FR"]
    assert rows
    assert {(r["Thickness1"], r["Thickness2"]) for r in rows} == {(None, None)}


@pytest.mark.parametrize("flange_type", ["WN", "SW"])
def test_reducing_flange_schedule_follows_small_end(tmp_path, flange_type):
    # 3-11: ASME B16.5 §6.8.2 — FR 허브는 작은 쪽(Size2) 배관에 맞춤. 큰 쪽(Size1)은 면·볼트 구멍 기준.
    bundle = build_sample_bundle()
    f = next(r for r in bundle.component_rows["Flange_Group"] if r["Item_Code"] == "F")
    # Size1 2~4 는 Schedule STD, Size2 1 은 SCH80 (sample_data.schedule_rows)
    fr = dict(f, Item_Code="FR", Flange_Type=flange_type, Size1_From="2", Size1_To="4",
              Size2_From="1", Size2_To="1")
    bundle.component_rows["Flange_Group"].append(fr)
    rows = [r for r in _generate(bundle, tmp_path) if r["Item_Code"] == "FR"]
    assert rows
    assert {(r["Thickness1"], r["Thickness2"]) for r in rows} == {(None, "SCH80")}
    assert all(r["Item_Description"].endswith(" SCH80") for r in rows), [r["Item_Description"] for r in rows]


def test_load_canonicalizes_legacy_notation():
    # 대문자 통일·CL 표기 통일 이전에 저장된 프로젝트도 불러오면 현행 목록 값으로 맞춰진다.
    bundle = build_sample_bundle()
    va = bundle.component_rows["Gate_Valve_Group"][0]
    bundle.component_rows["Gate_Valve_Group"][0] = dict(va, Rating="150#", Trim_Matl="13Cr")
    loaded = bundle_from_json_dict(bundle_to_json_dict(bundle))
    row = loaded.component_rows["Gate_Valve_Group"][0]
    assert (row["Rating"], row["Trim_Matl"]) == ("CL150", "13CR")
    assert loaded.validate() == []


def test_load_keeps_values_it_cannot_map():
    # 맞출 수 없는 값은 그대로 둔다 — 저장 단계 검사가 막는다.
    bundle = build_sample_bundle()
    b = bundle.component_rows["Bolt_Group"][0]
    bundle.component_rows["Bolt_Group"][0] = dict(b, Bolt_Length_Table="LT-A")
    loaded = bundle_from_json_dict(bundle_to_json_dict(bundle))
    assert loaded.component_rows["Bolt_Group"][0]["Bolt_Length_Table"] == "LT-A"
    assert any("LT-A" in e for e in loaded.validate())
