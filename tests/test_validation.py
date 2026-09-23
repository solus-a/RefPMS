"""체크리스트 2-4: GUI 가 쓰는 검증 함수 — 필수 / 조건부 필수 / 크기 / Class_Define."""
from __future__ import annotations

import pytest

from class_level_model import (
    NamedSizeTable,
    component_row_constraint_errors,
    component_row_missing_required,
    component_row_size_pair_errors,
)
from data_defaults import DEFAULT_COMPONENT_MAPPING
from sample_data import CLASS, class_row, component_rows
from validator import validate_template_row_dict


def _first(sheet: str, item_code: str) -> dict[str, str]:
    return dict(next(r for r in component_rows()[sheet] if r["Item_Code"] == item_code))


# ── Component 필수 / 조건부 필수 ─────────────────────────────────────────────

def test_all_sample_component_rows_pass():
    for sheet, rows in component_rows().items():
        for row in rows:
            assert component_row_missing_required(sheet, row) == [], (sheet, row["Item_Code"])
            assert component_row_size_pair_errors(sheet, row) == [], (sheet, row["Item_Code"])


def test_required_field_empty_is_reported():
    row = _first("Pipe_Group", "P")
    row["Matl_Code"] = ""
    assert component_row_missing_required("Pipe_Group", row) == ["Matl_Code"]


def test_field_absent_from_form_is_not_reported():
    # Class_Name 은 폼에 없고 저장 단계에서 채워진다 — 키가 없으면 검사 대상 아님.
    row = _first("Pipe_Group", "P")
    del row["Class_Name"]
    assert component_row_missing_required("Pipe_Group", row) == []


def test_nipple_requires_length_but_pipe_does_not():
    nipple = _first("Pipe_Group", "JN")
    nipple["Length"] = ""
    assert component_row_missing_required("Pipe_Group", nipple) == ["Length"]
    assert component_row_missing_required("Pipe_Group", _first("Pipe_Group", "P")) == []


def test_reducing_flange_requires_size2():
    row = _first("Flange_Group", "F")
    row["Item_Code"] = "FR"
    assert component_row_missing_required("Flange_Group", row) == ["Size2_From", "Size2_To"]


def test_blind_flange_does_not_require_flange_type():
    # F10 해결: Flange_Type 은 F/FR 일 때만 필수.
    row = _first("Flange_Group", "F")
    row.update(Item_Code="FB", Flange_Type="")
    assert component_row_missing_required("Flange_Group", row) == []


def test_plain_flange_requires_flange_type():
    row = _first("Flange_Group", "F")
    row["Flange_Type"] = ""
    assert component_row_missing_required("Flange_Group", row) == ["Flange_Type"]


@pytest.mark.parametrize("item_code", ["FB", "F8", "FBS"])
def test_engine_rejects_flange_type_on_blind_items(item_code):
    row = dict(_first("Flange_Group", "F"), Item_Code=item_code)  # Flange_Type=WN 남아 있음
    msgs = validate_template_row_dict("Flange_Group", 2, row, DEFAULT_COMPONENT_MAPPING)
    assert any("Flange_Type" in m for m in msgs), msgs


def test_bolt_length_table_is_optional():
    row = _first("Bolt_Group", "B")
    row["Bolt_Length_Table"] = ""
    assert component_row_missing_required("Bolt_Group", row) == []


# ── Forged End_Type ↔ Rating (ASME B16.11 §2.1) ─────────────────────────────

@pytest.mark.parametrize(
    "end_type, rating, ok",
    [
        ("SW", "CL3000", True),
        ("SW", "CL9000", True),
        ("SW", "CL2000", False),   # 2000 은 나사식 전용
        ("NPT", "CL2000", True),
        ("PT", "CL6000", True),
        ("PT", "CL9000", False),   # 9000 은 소켓웰드 전용
        ("NPT", "CL9000", False),
        ("SW", "SCH80", True),     # JIS·KS Sch80 은 규칙 대상 아님
        ("sw ", "cl2000", False),  # 대소문자·공백 무시
    ],
)
def test_forged_end_type_rating_constraint(end_type, rating, ok):
    row = dict(_first("Forged_Fitting_Group", "E"), End_Type=end_type, Rating=rating)
    errors = component_row_constraint_errors("Forged_Fitting_Group", row)
    assert (errors == []) is ok, errors


def test_engine_applies_forged_constraint():
    row = dict(_first("Forged_Fitting_Group", "E"), End_Type="SW", Rating="CL2000")
    msgs = validate_template_row_dict("Forged_Fitting_Group", 5, row, DEFAULT_COMPONENT_MAPPING)
    assert any("ASME B16.11" in m and "row 5" in m for m in msgs), msgs


def test_constraint_does_not_touch_other_groups():
    row = dict(_first("Flange_Group", "F"), Rating="CL2000")
    assert component_row_constraint_errors("Flange_Group", row) == []


def test_spiral_wound_gasket_requires_secondary_material():
    row = _first("Gasket_Group", "G")
    row.update(Gasket_Type="SPIRAL WOUND", Material_Secondary="")
    assert component_row_missing_required("Gasket_Group", row) == ["Material_Secondary"]
    row["Gasket_Type"] = "SHEET"
    assert component_row_missing_required("Gasket_Group", row) == []


def test_pipe_size_from_greater_than_to_is_error():
    row = _first("Pipe_Group", "P")
    row.update(Size_From="4", Size_To="2")
    assert component_row_size_pair_errors("Pipe_Group", row) == ["Size_From (4) > Size_To (2)"]


# ── Bundle / Class_Define ──────────────────────────────────────────────────

def test_sample_bundle_is_valid(sample_bundle):
    assert sample_bundle.validate() == []
    assert sample_bundle.class_define_value_errors(CLASS) == []
    assert sample_bundle.class_define_missing_fields(CLASS) == []


def test_size_outside_global_selection_is_error(sample_bundle):
    sample_bundle.class_define_rows = [class_row(Size_From="1.25")]
    errs = sample_bundle.validate()
    assert any("Size_From '1.25' is not in the Global Size Selection" in e for e in errs)


def test_size_to_below_size_from_is_error(sample_bundle):
    sample_bundle.class_define_rows = [class_row(Size_From="4", Size_To="2")]
    assert any("Size_To must be greater than or equal to Size_From" in e for e in sample_bundle.validate())


def test_unregistered_table_reference_is_error(sample_bundle):
    sample_bundle.class_define_rows = [class_row(Reducing_Table_1="RT-X")]
    assert any("not a registered reducing table name" in e for e in sample_bundle.validate())


def test_table_nominal_mode_must_match_class(sample_bundle):
    sample_bundle.reducing_tables = [NamedSizeTable("RT-1", [], nominal_mode="DN")]
    sample_bundle.class_define_rows = [class_row(Reducing_Table_1="RT-1")]
    assert any("nominal mode is DN" in e for e in sample_bundle.validate())


def test_duplicate_table_code_is_error(sample_bundle):
    sample_bundle.reducing_tables = [NamedSizeTable("T1", [])]
    sample_bundle.branch_tables = [NamedSizeTable("T1", [])]
    assert any("Duplicate Table_Code" in e for e in sample_bundle.validate())


def test_non_numeric_corrosion_allowance_is_error(sample_bundle):
    sample_bundle.class_define_rows = [class_row(Corrosion_Allowance="abc")]
    assert any("Corrosion_Allowance must be numeric" in e for e in sample_bundle.validate())


def test_disallowed_schedule_value_is_error(sample_bundle):
    sample_bundle.schedule_rows[0]["Schedule"] = "SCH999"
    assert any("Schedule value 'SCH999' is not allowed" in e for e in sample_bundle.validate())


def test_design_temperature_from_above_to_is_error(sample_bundle):
    sample_bundle.class_define_rows = [
        class_row(Design_Temperature_From="300", Design_Temperature_To="200")
    ]
    assert sample_bundle.class_define_value_errors(CLASS) == [
        "Design_Temperature: From (300.0) > To (200.0)"
    ]


def test_missing_class_field_and_schedule_are_listed(sample_bundle):
    sample_bundle.class_define_rows = [class_row(Design_Code="")]
    sample_bundle.schedule_rows = []
    missing = sample_bundle.class_define_missing_fields(CLASS)
    assert "Design_Code" in missing
    assert "Schedule (no rows defined for this class)" in missing
