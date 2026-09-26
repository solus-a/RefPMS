"""Component 행 편집 다이얼로그 — 필터·잠금·기존 값 보존 (tk 창을 띄우되 루트는 숨김)."""
from __future__ import annotations

import tkinter as tk

import pytest

from class_template_wizard import COMPONENT_GROUPS, _ComponentRowEditDialog
from sample_data import SELECTED_NPS, component_rows

HEADERS = {sheet: headers for sheet, _label, headers in COMPONENT_GROUPS}


# Tk 루트는 모듈에서 하나만 — 한 프로세스에서 Tk() 를 파괴 후 다시 만들면
# Windows 에서 'tcl_findLibrary' 오류가 난다.
@pytest.fixture(scope="module")
def root():
    try:
        r = tk.Tk()
    except tk.TclError as exc:  # 디스플레이가 없는 환경
        pytest.skip(f"tk unavailable: {exc}")
    r.withdraw()
    yield r
    r.destroy()


def _dialog(root, sheet: str, initial: dict[str, str]) -> _ComponentRowEditDialog:
    return _ComponentRowEditDialog(
        root, title="test", sheet_name=sheet, headers=HEADERS[sheet],
        active_sizes=list(SELECTED_NPS), initial=initial,
    )


def _first(sheet: str, item_code: str) -> dict[str, str]:
    return dict(next(r for r in component_rows()[sheet] if r["Item_Code"] == item_code))


def _display_for(dlg, field: str, stored: str) -> str:
    return next(d for d, s in dlg._reverse_maps[field].items() if s == stored)


def test_forged_rating_follows_end_type(root):
    # 기존 행이 SW + CL2000 (B16.11 위반) → 열자마자 Rating 이 비워지고 후보에서 CL2000 이 빠진다.
    dlg = _dialog(root, "Forged_Fitting_Group", dict(_first("Forged_Fitting_Group", "E"), Rating="CL2000"))
    try:
        assert dlg._vars["Rating"].get() == ""
        values = list(dlg._combo_widgets["Rating"].cget("values"))
        assert "CL2000" not in values and "CL9000" in values
        assert values.count("SCH80") == 1  # JIS·KS 중복 표시 제거

        dlg._vars["End_Type"].set(_display_for(dlg, "End_Type", "PT"))
        dlg._apply_forged_rating_filter()
        values = list(dlg._combo_widgets["Rating"].cget("values"))
        assert "CL2000" in values and "CL9000" not in values
    finally:
        dlg.destroy()


def test_blind_flange_locks_flange_type(root):
    dlg = _dialog(root, "Flange_Group", dict(_first("Flange_Group", "F"), Item_Code="FB"))
    try:
        assert dlg._vars["Flange_Type"].get() == ""
        assert str(dlg._field_widgets["Flange_Type"].cget("state")) == "disabled"

        dlg._vars["Item_Code"].set("F")
        dlg._apply_flange_type_lock()
        assert str(dlg._field_widgets["Flange_Type"].cget("state")) == "readonly"
    finally:
        dlg.destroy()


def test_legacy_value_is_shown_but_save_is_blocked(root, monkeypatch):
    # 선택 입력 필드의 옛 자유 입력 값: 창에는 그대로 보이지만(조용히 지우지 않음) 저장은 막힌다.
    import class_template_wizard as w
    shown = []
    monkeypatch.setattr(w.messagebox, "showerror", lambda title, msg, **k: shown.append(msg))
    dlg = _dialog(root, "Bolt_Group", dict(_first("Bolt_Group", "B"), Bolt_Length_Table="LT-A"))
    try:
        assert dlg._vars["Bolt_Length_Table"].get() == "LT-A"
        dlg._ok()
        assert dlg.result is None
        assert shown and "Bolt_Length_Table 'LT-A' is not in the Bolt_Length_Table list" in shown[0]
    finally:
        if dlg.winfo_exists():
            dlg.destroy()


def test_legacy_value_in_required_field_is_not_kept(root):
    # 필수 필드: 목록에 없는 옛 값(예: CL 통일 전 '150#')은 빈칸으로 보여 다시 고르게 한다.
    dlg = _dialog(root, "Gate_Valve_Group", dict(_first("Gate_Valve_Group", "VA"), Rating="150#"))
    try:
        assert dlg._vars["Rating"].get() == ""
        assert "150#" not in dlg._combo_widgets["Rating"].cget("values")
    finally:
        dlg.destroy()
