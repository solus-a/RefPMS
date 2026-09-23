"""체크리스트 2-2: GUI Export → pms_generator 전체 흐름.

xfail(strict) 는 docs/V1_CHECKLIST.md 의 발견 사항(F번호)과 1:1 대응하는 *알려진 결함*이다.
고치면 XPASS 가 되어 실패하므로, 그때 해당 xfail 마커를 지운다.
"""
from __future__ import annotations

import pytest

import domain_schema
from class_level_model import SizeSelection
from class_template_wizard import _combined_component_name
from template_generator import load_class_level_bundle_from_template

# 산출물에는 그룹 컬럼이 없다. sample_data 는 같은 Item_Code 를 쓰는 그룹끼리 크기 범위가
# 겹치지 않으므로 (Item_Code, Size1) 로 원래 Component 행을 찾는다.
_SIZE_FROM = ("Size_From", "Size1_From")
_SIZE_TO = ("Size_To", "Size1_To")


def _source_row(bundle, item_code: str, size: str) -> tuple[str, dict[str, str]]:
    s = float(size)
    for sheet, rows in bundle.component_rows.items():
        for row in rows:
            if row["Item_Code"] != item_code:
                continue
            lo = next(row[k] for k in _SIZE_FROM if k in row)
            hi = next(row[k] for k in _SIZE_TO if k in row)
            if float(lo) <= s <= float(hi):
                return sheet, row
    raise LookupError(f"no source row for {item_code} {size}")


def _code_name(sheet: str, item_code: str) -> str:
    for entry in domain_schema.item_code_entries(sheet):
        if entry.get("code") == item_code:
            return entry.get("code_name", "")
    return ""


# ── 현재 통과해야 하는 것 ──────────────────────────────────────────────────

def test_template_round_trip_keeps_component_rows(generated):
    loaded = load_class_level_bundle_from_template(generated.template_path)
    for sheet, rows in generated.bundle.component_rows.items():
        assert loaded.component_rows.get(sheet) == rows, sheet


def test_template_round_trip_keeps_class_and_schedule(generated):
    loaded = load_class_level_bundle_from_template(generated.template_path)
    assert loaded.class_define_rows == generated.bundle.class_define_rows
    assert loaded.schedule_rows == generated.bundle.schedule_rows
    assert loaded.global_settings == generated.bundle.global_settings


def test_generator_outputs_every_item_code(generated):
    expected = {r["Item_Code"] for rows in generated.bundle.component_rows.values() for r in rows}
    assert {r["Item_Code"] for r in generated.rows} == expected


def test_every_output_row_maps_back_to_a_component_row(generated):
    for r in generated.rows:
        _source_row(generated.bundle, r["Item_Code"], r["Size1"])


# ── 알려진 결함 (체크리스트 F번호) ─────────────────────────────────────────

@pytest.mark.xfail(reason="F1: 생성기가 레거시 Item_Code_DB.xlsx 를 읽어 Fitting description 이 빈 값")
def test_every_row_has_description(generated):
    empty = sorted({r["Item_Code"] for r in generated.rows if not r["Item_Description"]})
    assert empty == []


@pytest.mark.xfail(reason="F2·F3: Item_Name 이 GUI 의 item_code_db.json(그룹별)과 다름")
def test_item_name_matches_item_code_db_json(generated):
    wrong = set()
    for r in generated.rows:
        sheet, _ = _source_row(generated.bundle, r["Item_Code"], r["Size1"])
        if r["Item_Name"] != _code_name(sheet, r["Item_Code"]):
            wrong.add((sheet, r["Item_Code"], r["Item_Name"]))
    assert sorted(wrong) == []


@pytest.mark.xfail(reason="F4: 생성기가 Global Size Selection 을 무시하고 카탈로그 전체 크기를 전개")
def test_sizes_respect_global_size_selection(generated):
    selection: SizeSelection = generated.bundle.global_settings.size_selection
    outside = sorted({r["Size1"] for r in generated.rows} - set(selection.nps), key=float)
    assert outside == []


@pytest.mark.xfail(reason="F5: 생성기 description 로직이 GUI _DESCRIPTION_SPECS 와 별개")
def test_description_matches_gui_preview(generated):
    # 산출물은 미리보기 뒤에 Class 연동 토큰(Schedule 등)이 더 붙을 수 있다.
    mismatched = set()
    for r in generated.rows:
        sheet, row = _source_row(generated.bundle, r["Item_Code"], r["Size1"])
        preview = _combined_component_name(sheet, row)
        desc = r["Item_Description"] or ""
        if desc != preview and not desc.startswith(preview + " "):
            mismatched.add((sheet, r["Item_Code"], preview, desc))
    assert sorted(mismatched) == []


@pytest.mark.xfail(reason="F6: Commodity Code 미구현")
def test_every_row_has_commodity_code(generated):
    assert [r["Item_Code"] for r in generated.rows if not r["Commodity_Code"]] == []


@pytest.mark.xfail(reason="F1·F7: Forged Fitting rating 이 CL 표기로 나와야 함 (현재 빈 값, 코드에는 # 역변환 잔존)")
def test_forged_fitting_rating_keeps_cl_notation(generated):
    forged = [
        r for r in generated.rows
        if _source_row(generated.bundle, r["Item_Code"], r["Size1"])[0] == "Forged_Fitting_Group"
    ]
    assert forged
    assert all("CL2000" in (r["Item_Description"] or "") for r in forged)
    assert not any("#" in (r["Item_Description"] or "") for r in generated.rows)
