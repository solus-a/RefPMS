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


def test_every_row_has_description(generated):
    # F1 해결: 생성기가 item_code_db.json 을 그룹별로 조회.
    empty = sorted({r["Item_Code"] for r in generated.rows if not r["Item_Description"]})
    assert empty == []


def test_item_name_matches_item_code_db_json(generated):
    # F2·F3 해결. Wrought 엘보는 LR/SR 을 유지한다 (ASME B16.9: LR·SR 은 치수표가 다른 별개 부품).
    # 니플(JN)만 길이로 식별하므로 code_name 뒤에 Length 가 붙는다.
    wrong = set()
    for r in generated.rows:
        sheet, row = _source_row(generated.bundle, r["Item_Code"], r["Size1"])
        expected = _code_name(sheet, r["Item_Code"])
        if r["Item_Code"] == "JN":
            expected = f"{expected} {row['Length']}"
        if r["Item_Name"] != expected:
            wrong.add((sheet, r["Item_Code"], r["Item_Name"], expected))
    assert sorted(wrong) == []


def test_sizes_respect_global_size_selection(generated):
    # F4 해결: 상위 제약(Class 범위 ∩ Global Size Selection) 밖의 크기는 전개하지 않는다.
    selection: SizeSelection = generated.bundle.global_settings.size_selection
    outside = sorted({r["Size1"] for r in generated.rows} - set(selection.nps), key=float)
    assert outside == []


def _forged_rows(generated):
    return [
        r for r in generated.rows
        if _source_row(generated.bundle, r["Item_Code"], r["Size1"])[0] == "Forged_Fitting_Group"
    ]


def test_forged_fitting_rating_keeps_cl_notation(generated):
    # F7 해결: CL3000 → 3000# 역변환 없음. Bushing(JB)은 class 로 식별하지 않아 등급 없음.
    forged = [r for r in _forged_rows(generated) if r["Item_Code"] != "JB"]
    assert forged
    assert all("CL3000" in r["Item_Description"] for r in forged)
    assert not any("#" in (r["Item_Description"] or "") for r in generated.rows)


def test_forged_fitting_thickness_is_rating(generated):
    # ASME B16.11 §2.1: 단조 피팅은 Class 로 식별 → Thickness1 은 Schedule 이 아니라 Rating.
    # Plug·Bushing 은 class 로 식별하지 않으므로 빈 값.
    by_code = {(r["Item_Code"], r["Thickness1"]) for r in _forged_rows(generated)}
    assert by_code == {("E", "CL3000"), ("T", "CL3000"), ("CP", "CL3000"), ("JFR", "CL3000"), ("JB", None)}


def test_forged_reducing_items_do_not_repeat_rating(generated):
    # 회귀 방지: JFR 직접 행이 Reducer 분기를 타서 "CL3000 CL3000" 이 찍히던 문제.
    descs = {r["Item_Code"]: r["Item_Description"] for r in _forged_rows(generated)}
    assert descs["JFR"] == "REDUCING FULL COUPLING A105 SW CL3000"
    assert descs["JB"] == "BUSHING A105 NPT"


def test_blind_flange_has_no_flange_type_or_schedule_in_description(generated):
    # F10 해결: Blind(FB)는 Flange_Type 이 없으므로 WN·Schedule 토큰이 붙지 않는다.
    descs = {r["Item_Description"] for r in generated.rows if r["Item_Code"] == "FB"}
    assert descs == {"BLIND FLANGE A105 CL150 RF"}


def test_wrought_fitting_thickness_is_schedule(generated):
    wrought = [
        r for r in generated.rows
        if _source_row(generated.bundle, r["Item_Code"], r["Size1"])[0] == "Wrought_Fitting_Group"
    ]
    assert wrought
    assert {r["Thickness1"] for r in wrought} == {"STD"}


# ── 알려진 결함 (체크리스트 F번호) ─────────────────────────────────────────

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
