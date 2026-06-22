"""Class-level template wizard (English UI) — runs before template xlsx is built."""

from __future__ import annotations

import copy
import json
import tkinter as tk
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Callable, Literal

import config
from class_level_model import (
    ClassLevelBundle,
    ClassTemplateGlobalSettings,
    NamedSizeTable,
    SizeSelection,
    component_row_missing_required,
    component_row_required_fields,
    component_row_size_pair_errors,
    default_size_selection_from_catalog,
    normalizeScheduleValue,
    row_dict_for_headers,
    scheduleAllowlist,
)
from class_spec import class_base_material_group_keys, flange_pt_class_rating_options
from size_matrix_common import normalize_nominal_mode
from size_matrix_editor import run_size_matrix_editor
from template_generator import (
    COMPONENT_GROUP_DEFS as COMPONENT_GROUPS,
    DEFAULT_TEMPLATE_FILENAME,
    SCHEDULE_HEADERS,
    generate_class_define_template,
)
from units_notation_headers import bracket_unit_header, class_define_storage_headers
import file_handler
from project_codec import ProjectFileError, save_project

_CLASS_DETAIL_LABEL_WIDTH = 28
_CLASS_DETAIL_VALUE_PADX = (8, 0)

# Light-theme list / sheet visuals (zebra ≈ thin row separation)
_STRIPE_A = "#ffffff"
_STRIPE_B = "#f0f1f4"
_LIST_HOVER = "#dceaf7"

_CORROSION_ALLOWANCE_KEY = "Corrosion_Allowance"


def _corrosion_allowance_unit_symbol(unit_system: str) -> str:
    return "inch" if unit_system == "US Customary" else "mm"


def _corrosion_reference_values_for(unit_system: str) -> list[str]:
    """Corrosion_Allowance 참조 값 목록 — Unit_System (SI/US Customary) 에 따라 결정."""
    ref = config.config_manager.get(
        "validation_policy.corrosion_allowance.reference_values", {}
    )
    if not isinstance(ref, dict):
        return []
    key = "imperial_inch" if unit_system == "US Customary" else "metric_mm"
    raw = ref.get(key)
    if not isinstance(raw, list):
        return []
    ordered: list[str] = []
    seen: set[str] = set()
    for v in raw:
        sv = str(v or "").strip()
        if not sv or sv in seen:
            continue
        seen.add(sv)
        ordered.append(sv)
    return ordered


def _all_codes(bundle: ClassLevelBundle) -> set[str]:
    return {t.table_code.strip() for t in bundle.reducing_tables + bundle.branch_tables if t.table_code.strip()}


def _listbox_apply_stripes(lb: tk.Listbox, hover_idx: int | None = None) -> None:
    n = lb.size()
    sel = lb.curselection()
    sel_i = int(sel[0]) if sel else None
    for i in range(n):
        try:
            if sel_i is not None and i == sel_i:
                continue
            bg = _LIST_HOVER if hover_idx is not None and i == hover_idx else (_STRIPE_B if i % 2 else _STRIPE_A)
            lb.itemconfigure(i, background=bg)
        except tk.TclError:
            return


def _bind_listbox_stripes_and_hover(lb: tk.Listbox) -> None:
    hover: dict[str, int | None] = {"i": None}

    def paint(_e: tk.Event | None = None) -> None:
        _listbox_apply_stripes(lb, hover["i"])

    def motion(e: tk.Event) -> None:
        try:
            idx = lb.nearest(e.y)
        except tk.TclError:
            return
        if idx < 0 or idx >= lb.size():
            return
        if lb.curselection() and int(lb.curselection()[0]) == idx:
            if hover["i"] != idx:
                hover["i"] = None
                paint()
            return
        if hover["i"] == idx:
            return
        hover["i"] = idx
        paint()

    def leave(_e: tk.Event | None = None) -> None:
        hover["i"] = None
        paint()

    lb.bind("<Motion>", motion, add="+")
    lb.bind("<Leave>", leave, add="+")
    lb.bind("<<ListboxSelect>>", paint, add="+")


def _canvas_dashed_empty_state(
    parent: tk.Misc,
    message: str,
    *,
    height: int = 120,
    bg: str = "#fafafa",
) -> tk.Canvas:
    c = tk.Canvas(parent, height=height, bg=bg, highlightthickness=0)

    def draw(_event: tk.Event | None = None) -> None:
        c.update_idletasks()
        w = max(c.winfo_width(), 120)
        h = max(c.winfo_height(), height)
        c.delete("all")
        c.create_rectangle(10, 8, w - 10, h - 8, dash=(5, 3), outline="#a8a8a8", width=1)
        c.create_text(w // 2, h // 2, text=message, fill="#777777", font=("Segoe UI", 10))

    c.bind("<Configure>", draw)
    return c


def _configure_sheet_treeview_style() -> None:
    style = ttk.Style()
    style.configure(
        "WizardSheet.Treeview",
        rowheight=22,
        borderwidth=0,
        fieldbackground=_STRIPE_A,
    )
    style.map(
        "WizardSheet.Treeview",
        background=[("selected", "#2b6cb0")],
        foreground=[("selected", "white")],
    )
    style.configure(
        "WizardSchedule.Treeview",
        rowheight=24,
        borderwidth=1,
        relief="solid",
        fieldbackground=_STRIPE_A,
    )
    style.map(
        "WizardSchedule.Treeview",
        background=[("selected", "#c7dbf4")],
        foreground=[("selected", "#1f2d3d")],
    )
    style.configure("Warn.TCombobox", fieldbackground="#ffcccc")
    style.map(
        "Warn.TCombobox",
        fieldbackground=[
            ("readonly", "#ffcccc"),
            ("disabled", "#ffcccc"),
            ("!disabled", "#ffcccc"),
        ],
    )
    style.configure("Invalid.TEntry", fieldbackground="#ffd6d6")
    style.map(
        "Invalid.TEntry",
        fieldbackground=[
            ("readonly", "#ffd6d6"),
            ("disabled", "#ffd6d6"),
            ("!disabled", "#ffd6d6"),
            ("focus", "#ffd6d6"),
        ],
    )


def _tree_row_tags(row_index: int) -> tuple[str, ...]:
    return ("odd",) if row_index % 2 else ("even",)


def _tree_setup_tags(tree: ttk.Treeview) -> None:
    tree.tag_configure("even", background=_STRIPE_A)
    tree.tag_configure("odd", background=_STRIPE_B)
    tree.tag_configure("hover", background=_LIST_HOVER)
    tree.tag_configure("size_warn", background="#fff3cd", foreground="#856404")

    hover_state: dict[str, str | None] = {"iid": None}

    def clear_hover_tag(iid: str) -> None:
        tags = [t for t in tree.item(iid, "tags") if t != "hover"]
        tree.item(iid, tags=tuple(tags))

    def paint_hover(_e: tk.Event | None = None) -> None:
        prev = hover_state["iid"]
        if prev:
            try:
                if tree.exists(prev):
                    clear_hover_tag(prev)
            except tk.TclError:
                pass
            hover_state["iid"] = None

    def motion(e: tk.Event) -> None:
        iid = tree.identify_row(e.y)
        sel = tree.selection()
        if iid and sel and iid in sel:
            paint_hover()
            return
        prev = hover_state["iid"]
        if prev == iid:
            return
        paint_hover()
        if iid and tree.exists(iid):
            tags = list(tree.item(iid, "tags"))
            if "hover" not in tags:
                tree.item(iid, tags=tuple(tags + ["hover"]))
            hover_state["iid"] = iid

    def leave(_e: tk.Event | None = None) -> None:
        paint_hover()

    tree.bind("<Motion>", motion, add="+")
    tree.bind("<Leave>", leave, add="+")

    def on_select(_e: tk.Event | None = None) -> None:
        paint_hover()

    tree.bind("<<TreeviewSelect>>", on_select, add="+")


def _edit_row_dict_dialog(
    parent: tk.Toplevel,
    title: str,
    headers: list[str],
    row: dict[str, str],
) -> dict[str, str] | None:
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.grab_set()
    vars_map: dict[str, tk.StringVar] = {}
    for i, h in enumerate(headers):
        ttk.Label(win, text=h).grid(row=i, column=0, sticky="w", padx=8, pady=2)
        v = tk.StringVar(value=row.get(h, ""))
        vars_map[h] = v
        ttk.Entry(win, textvariable=v, width=48).grid(row=i, column=1, sticky="ew", padx=8, pady=2)
    win.columnconfigure(1, weight=1)
    result: dict[str, str] | None = None

    def on_ok() -> None:
        nonlocal result
        result = {h: vars_map[h].get().strip() if vars_map[h].get() else "" for h in headers}
        win.destroy()

    def on_cancel() -> None:
        win.destroy()

    bf = ttk.Frame(win)
    bf.grid(row=len(headers), column=0, columnspan=2, pady=10)
    ttk.Button(bf, text="OK", command=on_ok).pack(side="left", padx=6)
    ttk.Button(bf, text="Cancel", command=on_cancel).pack(side="left", padx=6)
    parent.wait_window(win)
    return result


def _edit_size_table_dialog(
    parent: tk.Toplevel,
    title: str,
    table: NamedSizeTable,
    pair_kind: Literal["reducing", "branch"],
    nominal_mode: str | None = None,
    size_selection: SizeSelection | None = None,
) -> NamedSizeTable | None:
    return run_size_matrix_editor(parent, title, table, pair_kind, nominal_mode, size_selection)


def _ask_nominal_mode_dialog(parent: tk.Widget) -> str | None:
    """NPS / DN 라디오 버튼 선택 모달. 선택된 모드 문자열 반환, 취소시 None."""
    result: dict[str, str | None] = {"mode": None}
    win = tk.Toplevel(parent)
    win.title("Select Nominal Size System")
    win.resizable(False, False)
    win.transient(parent)
    win.grab_set()

    var = tk.StringVar(value="NPS")
    rb_frame = ttk.Frame(win)
    rb_frame.pack(padx=20, pady=(16, 8))
    ttk.Radiobutton(rb_frame, text="NPS", variable=var, value="NPS").pack(anchor="w", pady=4)
    ttk.Radiobutton(rb_frame, text="DN", variable=var, value="DN").pack(anchor="w", pady=4)

    def on_ok() -> None:
        result["mode"] = var.get()
        win.destroy()

    def on_cancel() -> None:
        win.destroy()

    bf = ttk.Frame(win)
    bf.pack(pady=(8, 16))
    ttk.Button(bf, text="OK", command=on_ok).pack(side="left", padx=8)
    ttk.Button(bf, text="Cancel", command=on_cancel).pack(side="left", padx=8)
    parent.wait_window(win)
    return result["mode"]


def _build_named_tables_panel(
    container: tk.Widget,
    parent: tk.Toplevel,
    tables: list[NamedSizeTable],
    bundle: ClassLevelBundle,
    *,
    pair_kind: Literal["reducing", "branch"],
    refresh_dropdowns: Callable[[], None],
    nominal_mode_provider: Callable[[], str],
    size_selection_provider: Callable[[], SizeSelection],
) -> Callable[[], None]:
    """Reducing/Branch 테이블 관리 UI 를 주어진 container 에 렌더링.

    Returns a callable that refills the listbox (for external refresh after bundle state changes).
    """
    shell = tk.Frame(
        container,
        highlightthickness=1,
        highlightbackground="#b0b0b0",
        highlightcolor="#b0b0b0",
        bg="#fafafa",
    )
    holder = tk.Frame(shell, bg="#fafafa")
    lb = tk.Listbox(
        holder,
        height=12,
        exportselection=False,
        relief="flat",
        bd=0,
        highlightthickness=0,
        bg=_STRIPE_A,
        selectbackground="#2b6cb0",
        selectforeground="white",
        activestyle="none",
    )
    lb.pack(fill="both", expand=True, padx=1, pady=1)
    ph = _canvas_dashed_empty_state(shell, 'No tables yet. Use "Add".', height=140, bg="#fafafa")
    shell.pack(fill="both", expand=True, padx=8, pady=8)

    def refill() -> None:
        lb.delete(0, "end")
        for t in tables:
            lb.insert("end", t.table_code)
        if tables:
            ph.pack_forget()
            holder.pack(fill="both", expand=True)
        else:
            holder.pack_forget()
            ph.pack(fill="both", expand=True)
        _listbox_apply_stripes(lb)

    _bind_listbox_stripes_and_hover(lb)
    refill()

    def add_table() -> None:
        name = simpledialog.askstring("Add table", "Table_Code:", parent=parent)
        if not name or not name.strip():
            return
        name = name.strip()
        if name in _all_codes(bundle):
            messagebox.showerror("Duplicate", f"The name {name!r} is already in use.", parent=parent)
            return
        chosen_mode = _ask_nominal_mode_dialog(parent)
        if chosen_mode is None:
            return
        nt = NamedSizeTable(name, [], nominal_mode=chosen_mode)
        tables.append(nt)
        refill()
        lb.selection_clear(0, "end")
        lb.selection_set(len(tables) - 1)
        edited = _edit_size_table_dialog(
            parent,
            f"Edit table — {name}",
            nt,
            pair_kind,
            chosen_mode,
            size_selection=size_selection_provider(),
        )
        if edited:
            edited.nominal_mode = chosen_mode
            tables[-1] = edited
        else:
            tables.pop()
            refill()
        refresh_dropdowns()

    def edit_table() -> None:
        sel = lb.curselection()
        if not sel:
            messagebox.showinfo("Selection", "Select a table to edit.", parent=parent)
            return
        idx = int(sel[0])
        tbl = tables[idx]
        mode = tbl.nominal_mode if tbl.nominal_mode else nominal_mode_provider()
        edited = _edit_size_table_dialog(
            parent,
            f"Edit table — {tbl.table_code}",
            tbl,
            pair_kind,
            mode,
            size_selection=size_selection_provider(),
        )
        if edited:
            edited.nominal_mode = mode
            tables[idx] = edited
            refill()
        refresh_dropdowns()

    def del_table() -> None:
        sel = lb.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if messagebox.askyesno("Delete", "Delete this table?", parent=parent):
            tables.pop(idx)
            refill()
            refresh_dropdowns()

    bf = ttk.Frame(container)
    bf.pack(fill="x", padx=8, pady=(0, 8))
    ttk.Button(bf, text="Add", command=add_table).pack(side="left", padx=4)
    ttk.Button(bf, text="Edit", command=edit_table).pack(side="left", padx=4)
    ttk.Button(bf, text="Delete", command=del_table).pack(side="left", padx=4)

    return refill


# ── Component preview helpers ──────────────────────────────────────────────────

_STRUCTURAL_FIELDS: frozenset[str] = frozenset({
    "Class_Name", "Item_Code",
    "Size_From", "Size_To",
    "Size1_From", "Size1_To",
    "Size2_From", "Size2_To",
    "Remarks",
})
_SIZE1_SHEETS: frozenset[str] = frozenset({
    "Flange_Group",
    "Gate_Valve_Group", "Globe_Valve_Group", "Check_Valve_Group",
    "Ball_Valve_Group", "Butterfly_Valve_Group", "Plug_Valve_Group",
})
_SHEET_SIZE_FROM: dict[str, str] = {s: "Size1_From" for s in _SIZE1_SHEETS}
_SHEET_SIZE_TO:   dict[str, str] = {s: "Size1_To"   for s in _SIZE1_SHEETS}

_SIZE_FIELDS: frozenset[str] = frozenset({
    "Size_From", "Size_To", "Size1_From", "Size1_To", "Size2_From", "Size2_To",
})


def _combined_component_name(sheet_name: str, row: dict[str, str]) -> str:
    """Item_Description preview. Group별 결합 규칙이 정의된 시트는 전용 빌더, 그 외는 placeholder."""
    if sheet_name == "Pipe_Group":
        return _build_pipe_description(row)
    return " ".join(v.strip() for k, v in row.items() if k not in _STRUCTURAL_FIELDS and v.strip())


def _build_pipe_description(row: dict[str, str]) -> str:
    """Pipe_Group: <PREFIX> <Matl_Code> <Manufacturing_Method> <End_Type> [<Length>] [<Remarks>].
    PREFIX 는 Item_Code → item_code_db.json 의 code_name (P→PIPE, JN→NIPPLE).
    Schedule 은 Class 의 Size→Schedule 매핑에서 결정되므로 미리보기에서는 토큰 생략.
    빈 토큰은 통째로 생략, 구분자는 공백 한 칸."""
    code = (row.get("Item_Code") or "").strip().upper()
    prefix = ""
    for entry in _item_code_db_json().get("Pipe_Group", []) or []:
        if (entry.get("code") or "").strip().upper() == code:
            prefix = (entry.get("code_name") or "").strip()
            break
    tokens = [
        prefix,
        (row.get("Matl_Code") or "").strip(),
        (row.get("Manufacturing_Method") or "").strip(),
        (row.get("End_Type") or "").strip(),
        (row.get("Length") or "").strip(),
        (row.get("Remarks") or "").strip(),
    ]
    return " ".join(t for t in tokens if t)


# ── Numeric input validators ───────────────────────────────────────────────────

def _is_signed_decimal_proposal(proposed: str) -> bool:
    """Partial-input filter for signed decimals: '', '-', '-1', '-1.5', '0.5' 모두 허용."""
    if proposed in ("", "-"):
        return True
    s = proposed[1:] if proposed.startswith("-") else proposed
    if s.count(".") > 1:
        return False
    return all(ch.isdigit() or ch == "." for ch in s)


def _is_unsigned_decimal_proposal(proposed: str) -> bool:
    """Partial-input filter for unsigned decimals: '', '0', '0.5' 등."""
    if proposed == "":
        return True
    if proposed.count(".") > 1:
        return False
    return all(ch.isdigit() or ch == "." for ch in proposed)


def _parse_signed_decimal(value: str | None) -> float | None:
    raw = (value or "").strip()
    if not raw or raw == "-":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _normalize_decimal_string(raw: str | None) -> str:
    """소수 문자열의 표기 정규화: 앞 0 제거, 단 정수부가 0이면 한 자리 '0' 유지.
    소수부 trailing 0은 사용자 입력 의도로 보고 보존. 빈 값/'-'는 그대로 둠.

    예: '000' → '0', '005200.00' → '5200.00', '0.5' → '0.5', '-0.0' → '0.0'.
    """
    s = (raw or "").strip()
    if s in ("", "-"):
        return s
    sign = ""
    if s.startswith("-"):
        sign = "-"
        s = s[1:]
    if not s:
        return ""
    if "." in s:
        int_part, _, frac_part = s.partition(".")
        int_part = int_part.lstrip("0") or "0"
        result = f"{int_part}.{frac_part}"
    else:
        result = s.lstrip("0") or "0"
    if sign == "-" and all(ch in "0." for ch in result):
        sign = ""
    return f"{sign}{result}"


# ── Component field-value DB (per-group dropdown sources) ──────────────────────

@lru_cache(maxsize=1)
def _field_values_db() -> dict[str, dict[str, list[dict[str, str]]]]:
    path = config.field_values_db_path()
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f) or {}
    return {k: v for k, v in raw.items() if not k.startswith("_")}


@lru_cache(maxsize=1)
def _item_code_db_json() -> dict[str, list[dict[str, str]]]:
    path = config.item_code_db_json_path()
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f) or {}
    return {k: v for k, v in raw.items() if not k.startswith("_")}


# 약어를 풀어쓰지 않고 그대로(short) 표시할 필드 — 규격/등급/코드/재질 designation/길이.
# 저장값은 모든 필드에서 항상 short(엑셀 출력 contract 불변); 이 집합은 *표시값*만 결정한다.
_KEEP_SHORT_FIELDS: frozenset[str] = frozenset({
    "Item_Code",
    "Matl_Std", "Bolt_Matl_Std", "Nut_Matl_Std",
    "Matl_Code", "Bolt_Matl_Code", "Nut_Matl_Code",
    "Rating", "Option_Code",
    "Trim_Matl", "Seat_Matl", "Disc_Matl", "Plug_Matl",
    "Material_Primary", "Material_Secondary",
    "Bolt_Length_Table", "Bolt_Dim_Standard", "Nut_Dim_Standard",
})

# 비어 있는(=null) 저장값을 드롭다운에 노출할 때 쓰는 표시 라벨. 출력은 빈 값(없음).
_NONE_DISPLAY = "(None)"


def _field_display_label(field: str, item: dict[str, str]) -> str:
    """드롭다운 표시값. keep-short 필드는 short 그대로, 그 외 약어형 enum 은 long(띄어쓰기 포함).
    빈 저장값은 (None) 으로 표시."""
    short = (item.get("short", "") or "").strip()
    if not short:
        return _NONE_DISPLAY
    if field in _KEEP_SHORT_FIELDS:
        return short
    return (item.get("long", "") or "").strip() or short


def _group_display_label(label: str) -> str:
    """그룹 표시 라벨에서 'Group' 접미사 제거: 'Pipe Group' → 'Pipe'."""
    suffix = " Group"
    return label[: -len(suffix)] if label.endswith(suffix) else label


def _component_value_display(sheet_name: str, field: str, stored: str) -> str:
    """저장값(short)을 드롭다운과 동일한 표시 문자열로 변환. 매핑 없으면 원값."""
    if not stored:
        return ""
    opts = _options_for(sheet_name, field)
    if opts:
        return {s: d for s, d in opts}.get(stored, stored)
    return stored


def _options_for(sheet_name: str, field: str) -> list[tuple[str, str]] | None:
    """Returns [(stored_value, display_value), ...] or None if no DB entry for this group/field.
    저장값은 short(Item_Code 는 code); 표시값은 _field_display_label 규칙으로 풀어씀."""
    if field == "Item_Code":
        items = _item_code_db_json().get(sheet_name) or []
        if not items:
            return None
        return [(it.get("code", ""), it.get("code", "")) for it in items]
    items = (_field_values_db().get(sheet_name) or {}).get(field) or []
    if not items:
        return None
    return [(it.get("short", ""), _field_display_label(field, it)) for it in items]


_STD_FILTER_PAIRS: dict[str, str] = {
    "Matl_Code": "Matl_Std",
    "Bolt_Matl_Code": "Bolt_Matl_Std",
}


def _std_filtered_options_for(
    sheet_name: str, code_field: str, current_std: str
) -> list[tuple[str, str]] | None:
    """code_field 옵션 — 짝 std 가 정해지면 std 일치 항목만, 비면 전부."""
    items = (_field_values_db().get(sheet_name) or {}).get(code_field) or []
    if not items:
        return None
    std = (current_std or "").strip()
    if std:
        items = [it for it in items if (it.get("std") or "").strip() == std]
    if not items:
        return None
    return [(it.get("short", ""), _field_display_label(code_field, it)) for it in items]


# ── Component row editor ───────────────────────────────────────────────────────


class _ComponentRowEditDialog(tk.Toplevel):
    """Single-row field editor for Add / Edit in the component sheet."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        title: str,
        sheet_name: str,
        headers: list[str],
        active_sizes: list[str],
        initial: dict[str, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, True)
        self.transient(parent)
        self.grab_set()
        self.result: dict[str, str] | None = None

        form = ttk.Frame(self, padding=10)
        form.pack(fill="both", expand=True)

        self._sheet_name = sheet_name
        self._vars: dict[str, tk.StringVar] = {}
        self._reverse_maps: dict[str, dict[str, str]] = {}
        self._combo_widgets: dict[str, ttk.Combobox] = {}
        self._field_widgets: dict[str, tk.Widget] = {}

        size_options: list[tuple[str, str]] = [(s, s) for s in active_sizes]
        std_field_set = set(_STD_FILTER_PAIRS.values())
        self._required_fields = component_row_required_fields(sheet_name)

        for i, h in enumerate(headers):
            ttk.Label(form, text=h, width=24, anchor="e").grid(
                row=i, column=0, padx=(0, 6), pady=2, sticky="e"
            )

            if h in _SIZE_FIELDS:
                options: list[tuple[str, str]] | None = size_options or None
            elif h in _STD_FILTER_PAIRS:
                std_field = _STD_FILTER_PAIRS[h]
                initial_std = ((initial or {}).get(std_field, "") or "").strip()
                options = _std_filtered_options_for(sheet_name, h, initial_std)
            else:
                options = _options_for(sheet_name, h)

            options = self._with_none_option(h, options)
            initial_storage = ((initial or {}).get(h, "") or "").strip()

            if options:
                display_values = [d for _, d in options]
                storage_to_display = {s: d for s, d in options}
                self._reverse_maps[h] = {d: s for s, d in options}
                var = tk.StringVar(value=storage_to_display.get(initial_storage, ""))
                self._vars[h] = var
                cb = ttk.Combobox(
                    form, textvariable=var, values=display_values,
                    state="readonly", width=34,
                )
                cb.grid(row=i, column=1, pady=2, sticky="ew")
                self._combo_widgets[h] = cb
                self._field_widgets[h] = cb
                if h in std_field_set:
                    cb.bind(
                        "<<ComboboxSelected>>",
                        lambda _e, sf=h: self._refresh_dependent_code_options(sf),
                    )
            else:
                var = tk.StringVar(value=initial_storage)
                self._vars[h] = var
                entry = ttk.Entry(form, textvariable=var, width=34)
                entry.grid(row=i, column=1, pady=2, sticky="ew")
                self._field_widgets[h] = entry

        form.columnconfigure(1, weight=1)

        # Flange: Item_Code 가 FR 일 때만 Size2 입력 허용 — 그 외엔 잠금(비우고 disable).
        if self._sheet_name == "Flange_Group":
            ic_combo = self._combo_widgets.get("Item_Code")
            if ic_combo is not None:
                ic_combo.bind(
                    "<<ComboboxSelected>>",
                    lambda _e: self._apply_flange_size2_lock(),
                    add="+",
                )
            self._apply_flange_size2_lock()

        # Pipe: Length 는 Nipple (JN) Item_Code 일 때만 입력 허용 — 그 외엔 잠금(비우고 disable).
        if self._sheet_name == "Pipe_Group":
            ic_combo = self._combo_widgets.get("Item_Code")
            if ic_combo is not None:
                ic_combo.bind(
                    "<<ComboboxSelected>>",
                    lambda _e: self._apply_pipe_length_lock(),
                    add="+",
                )
            self._apply_pipe_length_lock()

        bf = ttk.Frame(self, padding=(10, 0, 10, 10))
        bf.pack(fill="x")
        ttk.Button(bf, text="OK",     command=self._ok).pack(side="right", padx=(4, 0))
        ttk.Button(bf, text="Cancel", command=self.destroy).pack(side="right")

        self.bind("<Return>", lambda _: self._ok())
        self.bind("<Escape>", lambda _: self.destroy())
        self.focus_force()

    def _with_none_option(
        self, field: str, options: list[tuple[str, str]] | None
    ) -> list[tuple[str, str]] | None:
        """옵션 목록 정규화: 빈 저장값 항목을 제거하고, 필수가 아닌 필드면 맨 앞에
        (None)→"" 선택지를 추가. 필수 필드는 (None) 없이 실제 값만."""
        if not options:
            return options
        cleaned = [(s, d) for (s, d) in options if (s or "").strip()]
        if field not in self._required_fields:
            cleaned = [("", _NONE_DISPLAY)] + cleaned
        return cleaned or None

    def _apply_flange_size2_lock(self) -> None:
        """Item_Code != FR 이면 Size2_From/To 를 비우고 잠근다. FR 이면 입력 허용."""
        ic_var = self._vars.get("Item_Code")
        # Item_Code 는 keep-short 라 표시값=저장값(code) 이므로 그대로 비교.
        is_fr = (ic_var.get() if ic_var is not None else "").strip().upper() == "FR"
        for f in ("Size2_From", "Size2_To"):
            w = self._field_widgets.get(f)
            if w is None:
                continue
            if is_fr:
                w.configure(state="readonly" if isinstance(w, ttk.Combobox) else "normal")
            else:
                var = self._vars.get(f)
                if var is not None:
                    var.set("")
                w.configure(state="disabled")

    def _apply_pipe_length_lock(self) -> None:
        """Item_Code != JN(Nipple) 이면 Length 를 비우고 잠근다. JN 이면 입력 허용."""
        ic_var = self._vars.get("Item_Code")
        # Item_Code 는 keep-short 라 표시값=저장값(code) 이므로 그대로 비교.
        is_nipple = (ic_var.get() if ic_var is not None else "").strip().upper() == "JN"
        w = self._field_widgets.get("Length")
        if w is None:
            return
        if is_nipple:
            w.configure(state="readonly" if isinstance(w, ttk.Combobox) else "normal")
        else:
            var = self._vars.get("Length")
            if var is not None:
                var.set("")
            w.configure(state="disabled")

    def _refresh_dependent_code_options(self, std_field: str) -> None:
        """std 필드 변경 시 짝이 되는 code 필드의 콤보 후보를 갱신."""
        code_field: str | None = None
        for cf, sf in _STD_FILTER_PAIRS.items():
            if sf == std_field:
                code_field = cf
                break
        if code_field is None or code_field not in self._combo_widgets:
            return
        std_var = self._vars.get(std_field)
        new_std = (std_var.get() if std_var is not None else "").strip()
        new_options = self._with_none_option(
            code_field, _std_filtered_options_for(self._sheet_name, code_field, new_std)
        ) or []
        new_display = [d for _, d in new_options]
        self._reverse_maps[code_field] = {d: s for s, d in new_options}
        self._combo_widgets[code_field].config(values=new_display)
        code_var = self._vars.get(code_field)
        if code_var is not None and code_var.get() not in new_display:
            code_var.set("")

    def _ok(self) -> None:
        out: dict[str, str] = {}
        for h, var in self._vars.items():
            raw = (var.get() or "").strip()
            if h in self._reverse_maps:
                out[h] = self._reverse_maps[h].get(raw, "")
            else:
                out[h] = raw

        missing = component_row_missing_required(self._sheet_name, out)
        if missing:
            messagebox.showwarning(
                "Missing required fields",
                f"{self._sheet_name} requires the following field(s):\n\n  • "
                + "\n  • ".join(missing),
                parent=self,
            )
            return

        size_errors = component_row_size_pair_errors(self._sheet_name, out)
        if size_errors:
            messagebox.showerror(
                "Invalid size range",
                "\n".join(f"  • {e}" for e in size_errors),
                parent=self,
            )
            return

        self.result = out
        self.destroy()


class ClassLevelWizard(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk,
        initial_bundle: ClassLevelBundle | None = None,
        initial_project_path: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.title("RefPMS")
        self.geometry("920x620")
        self.transient(parent)
        self.grab_set()
        self._project_path: str | None = initial_project_path
        self._material_combo_values = ["", *class_base_material_group_keys()]
        self._rating_combo_values = ["", *flange_pt_class_rating_options()]
        self._design_code_options: list[str] = ["", *config.design_codes_allowed()]
        self._nominal_size_options: list[str] = ["", *config.nominal_size_systems_allowed()]
        self._unit_system_options: list[str] = config.unit_systems_allowed()
        self._last_shown_class_idx: int | None = None

        self._corrosion_default_value = str(
            config.config_manager.get("validation_policy.corrosion_allowance.default_value", "0.0")
            or "0.0"
        ).strip() or "0.0"

        if initial_bundle is None:
            _si_units = config.design_units_for("SI")
            _t_def = str(((_si_units.get("temperature") or {}).get("default") or ""))
            _p_def = str(((_si_units.get("pressure") or {}).get("default") or ""))
            self._global_settings = ClassTemplateGlobalSettings(
                unit_system="SI",
                design_temperature_unit=_t_def,
                design_pressure_unit=_p_def,
                size_selection=default_size_selection_from_catalog(),
            )
            self._bundle = ClassLevelBundle(
                class_define_rows=[],
                schedule_rows=[],
                reducing_tables=[],
                branch_tables=[],
                global_settings=copy.deepcopy(self._global_settings),
            )
        else:
            self._bundle = copy.deepcopy(initial_bundle)
            self._global_settings = copy.deepcopy(self._bundle.global_settings)
            if not (self._global_settings.size_selection.nps or self._global_settings.size_selection.dn):
                self._global_settings.size_selection = default_size_selection_from_catalog()

        self._refresh_derived_from_global_settings()

        if not self._bundle.class_define_rows:
            self._bundle.class_define_rows = [self._new_class_row()]
        else:
            for row in self._bundle.class_define_rows:
                if not str(row.get(_CORROSION_ALLOWANCE_KEY, "") or "").strip():
                    row[_CORROSION_ALLOWANCE_KEY] = self._corrosion_default_value

        _configure_sheet_treeview_style()

        nb = ttk.Notebook(self)
        self._nb = nb
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self._reducing_tab_refresh: Callable[[], None] = lambda: None
        self._branch_tab_refresh: Callable[[], None] = lambda: None
        self._tab_global_setting(nb)
        self._tab_branch_tables(nb)
        self._tab_reducing_tables(nb)
        self._tab_class(nb)
        self._tab_components(nb)
        nb.bind("<<NotebookTabChanged>>", lambda _e: self._on_tab_changed())

        bf = ttk.Frame(self)
        bf.pack(fill="x", padx=8, pady=8)
        ttk.Button(bf, text="Close", command=self._on_close).pack(side="right", padx=6)
        ttk.Button(bf, text="Export xlsx", command=self._on_export_xlsx).pack(side="right", padx=6)
        ttk.Button(bf, text="Save Project", command=self._on_save_project).pack(side="right", padx=6)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._on_disk_snapshot: ClassLevelBundle = copy.deepcopy(self._bundle)

    def _refresh_derived_from_global_settings(self) -> None:
        """Global settings 변경 시 표시용 단위 라벨과 corrosion 레퍼런스를 재계산.

        class_define row dict 키는 단위에 무관한 storage 키로 고정되므로
        unit 변경 시에도 키 재매핑이 필요 없다.
        """
        gs = self._global_settings
        self._class_design_temp_u = gs.design_temperature_unit
        self._class_design_press_u = gs.design_pressure_unit
        self._class_define_headers = class_define_storage_headers()
        self._class_temp_from_h = "Design_Temperature_From"
        self._class_temp_to_h = "Design_Temperature_To"
        self._class_press_from_h = "Design_Pressure_From"
        self._class_press_to_h = "Design_Pressure_To"
        self._corrosion_unit_symbol = _corrosion_allowance_unit_symbol(gs.unit_system)
        self._corrosion_combo_values = _corrosion_reference_values_for(gs.unit_system)

    def _new_class_row(self) -> dict[str, str]:
        row = row_dict_for_headers(self._class_define_headers)
        row[_CORROSION_ALLOWANCE_KEY] = self._corrosion_default_value
        return row

    def _nominal_mode_for_class_name(self, class_name: str) -> str:
        """주어진 Class_Name 의 nominal_size_system (NPS/DN, 빈 값 시 NPS 폴백)."""
        target = (class_name or "").strip()
        for row in self._bundle.class_define_rows:
            if (row.get("Class_Name") or "").strip() == target:
                return normalize_nominal_mode(row.get("Nominal_Size_System"))
        return "NPS"

    def _catalog_all_for(self, mode: str) -> list[str]:
        return list(config.catalog_sizes_all(mode))

    def _catalog_preferred_for(self, mode: str) -> set[str]:
        return set(config.catalog_sizes_preferred(mode))

    def _selected_sizes_for_mode(self, mode: str) -> list[str]:
        """Global Setting Size Selection 에 따라 사용 가능한 사이즈를 카탈로그 순서로 반환."""
        sel = self._global_settings.size_selection
        active = set(sel.for_mode(mode))
        catalog = self._catalog_all_for(mode)
        if not active:
            return list(catalog)
        return [s for s in catalog if s in active]

    def _active_sizes_for_class(self, class_name: str) -> list[str]:
        """선택된 Global Sizes ∩ [Size_From..Size_To] for the given class name."""
        from class_level_model import _resolve_active_sizes
        target = (class_name or "").strip()
        for row in self._bundle.class_define_rows:
            if (row.get("Class_Name") or "").strip() != target:
                continue
            mode = normalize_nominal_mode(row.get("Nominal_Size_System"))
            sf = (row.get("Size_From") or "").strip()
            st = (row.get("Size_To") or "").strip()
            return _resolve_active_sizes(self._global_settings.size_selection, mode, sf, st)
        return []

    def _reducing_names(self) -> tuple[str, ...]:
        return ("", *tuple(t.table_code.strip() for t in self._bundle.reducing_tables if t.table_code.strip()))

    def _branch_names(self) -> tuple[str, ...]:
        return ("", *tuple(t.table_code.strip() for t in self._bundle.branch_tables if t.table_code.strip()))

    def _reducing_names_for_mode(self, mode: str) -> tuple[str, ...]:
        m = normalize_nominal_mode(mode)
        return (
            "",
            *tuple(
                t.table_code.strip()
                for t in self._bundle.reducing_tables
                if t.table_code.strip() and normalize_nominal_mode(t.nominal_mode) == m
            ),
        )

    def _branch_names_for_mode(self, mode: str) -> tuple[str, ...]:
        m = normalize_nominal_mode(mode)
        return (
            "",
            *tuple(
                t.table_code.strip()
                for t in self._bundle.branch_tables
                if t.table_code.strip() and normalize_nominal_mode(t.nominal_mode) == m
            ),
        )

    def _use_combined_temperature_pressure_rows(self) -> bool:
        return bool(
            self._class_temp_from_h
            and self._class_temp_to_h
            and self._class_press_from_h
            and self._class_press_to_h
        )

    def _on_revision_no_focus_out(self, _event: tk.Event | None = None) -> None:
        v = self._class_entries.get("Revision_No")
        if v is None:
            return
        cur = v.get() or ""
        up = cur.upper()
        if cur != up:
            v.set(up)

    def _on_class_name_focus_out(self, _event: tk.Event | None = None) -> None:
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        idx = self._current_class_idx()
        if idx is None:
            return
        name_var = self._class_entries.get("Class_Name")
        if name_var is None:
            return
        row = self._bundle.class_define_rows[idx]
        new_name = name_var.get() or ""
        row["Class_Name"] = new_name
        self._refresh_class_listbox()
        self._class_list.selection_clear(0, "end")
        self._class_list.selection_set(idx)
        self._class_list.activate(idx)
        self._class_list.see(idx)
        _listbox_apply_stripes(self._class_list)
        self._refresh_class_name_gate()

    def _on_size_range_selected(self, changed: str) -> None:
        """Size_From / Size_To 선택 시 From ≤ To 제약을 유지.

        위반 시 방금 변경된 쪽의 반대 콤보를 비워 사용자가 재선택하도록 한다.
        """
        cb_f = self._class_combos.get("Size_From")
        cb_t = self._class_combos.get("Size_To")
        if cb_f is None or cb_t is None:
            return
        val_f = cb_f.get()
        val_t = cb_t.get()
        if val_f and val_t:
            ns_cb = self._class_combos.get("Nominal_Size_System")
            mode = normalize_nominal_mode(ns_cb.get() if ns_cb else "")
            sizes = self._selected_sizes_for_mode(mode)
            try:
                if sizes.index(val_f) > sizes.index(val_t):
                    if changed == "Size_From":
                        cb_t.set("")
                    else:
                        cb_f.set("")
            except ValueError:
                pass
        self._save_class_detail_to_row()

    def _refresh_class_name_gate(self) -> None:
        """Class_Name 입력 여부에 따라 다른 모든 입력 위젯을 활성/비활성화."""
        name_var = self._class_entries.get("Class_Name")
        active = bool(name_var and name_var.get().strip())
        _EXEMPT = {"Class_Name", "Revision_No"}
        for h, widget in getattr(self, "_class_entry_widgets", {}).items():
            if h in _EXEMPT:
                continue
            widget.configure(state="normal" if active else "disabled")
        ns_cb = getattr(self, "_class_combos", {}).get("Nominal_Size_System")
        ns_active = active and bool(ns_cb and ns_cb.get().strip())
        _TABLE_REF_KEYS = {
            "Reducing_Table_1",
            "Reducing_Table_2",
            "Branch_Table_1",
            "Branch_Table_2",
        }
        for h, cb in getattr(self, "_class_combos", {}).items():
            if not active:
                cb.configure(state="disabled")
            elif h in ("Size_From", "Size_To"):
                cb.configure(state="readonly" if ns_active else "disabled")
            elif h in _TABLE_REF_KEYS:
                cb.configure(state="readonly" if ns_active else "disabled")
            else:
                normal_state = "normal" if h == _CORROSION_ALLOWANCE_KEY else "readonly"
                cb.configure(state=normal_state)
        sched_btn = getattr(self, "_schedule_edit_button", None)
        if sched_btn is not None:
            sched_btn.configure(state="normal" if active else "disabled")

    def _tab_global_setting(self, nb: ttk.Notebook) -> None:
        """Template 전역 단위 체계 + Size Selection 편집 탭 — 모든 Class 에 공통 적용."""
        tab = ttk.Frame(nb)
        nb.add(tab, text="Global Setting")

        box = ttk.LabelFrame(tab, text="Template-global unit system")
        box.pack(fill="x", padx=12, pady=(12, 6))

        lw = 22
        ttk.Label(box, text="Unit System", width=lw, anchor="w").grid(
            row=1, column=0, sticky="w", padx=8, pady=4
        )
        self._unit_system_var = tk.StringVar(value=self._global_settings.unit_system or "")
        radio_holder = ttk.Frame(box)
        radio_holder.grid(row=1, column=1, sticky="w", padx=(8, 8), pady=4)
        for option in self._unit_system_options:
            ttk.Radiobutton(
                radio_holder,
                text=option,
                value=option,
                variable=self._unit_system_var,
                command=self._on_unit_system_changed,
            ).pack(side="left", padx=(0, 12))

        ttk.Label(box, text="Design Temperature Unit", width=lw, anchor="w").grid(
            row=2, column=0, sticky="w", padx=8, pady=4
        )
        self._design_temp_var = tk.StringVar(value="")
        ttk.Label(box, textvariable=self._design_temp_var, anchor="w").grid(
            row=2, column=1, sticky="w", padx=(8, 8), pady=4
        )

        ttk.Label(box, text="Design Pressure Unit", width=lw, anchor="w").grid(
            row=3, column=0, sticky="w", padx=8, pady=4
        )
        self._design_press_combo = ttk.Combobox(box, width=28, state="readonly", values=[""])
        self._design_press_combo.grid(row=3, column=1, sticky="w", padx=(8, 8), pady=4)

        self._refresh_design_unit_options(preserve_selection=True)

        self._design_press_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._on_design_units_changed()
        )

        self._build_size_selection_panel(tab)

    def _build_size_selection_panel(self, parent: tk.Widget) -> None:
        """Global Size Selection panel — NPS / DN / Use 표 + Save 버튼."""
        box = ttk.LabelFrame(parent, text="Size Selection (Global)")
        box.pack(fill="y", expand=True, anchor="w", padx=12, pady=(6, 12))

        toolbar = ttk.Frame(box)
        toolbar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(toolbar, text="Save", command=lambda: self._save_size_selection()).pack(side="right")
        ttk.Button(
            toolbar,
            text="Defaults",
            command=lambda: self._reset_size_selection_to_preferred(),
        ).pack(side="right", padx=(0, 8))
        ttk.Button(
            toolbar,
            text="Select all",
            command=lambda: self._set_all_size_selection(True),
        ).pack(side="right", padx=(0, 8))
        ttk.Button(
            toolbar,
            text="Clear all",
            command=lambda: self._set_all_size_selection(False),
        ).pack(side="right", padx=(0, 8))

        scroll_host = ttk.Frame(box)
        scroll_host.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        scroll_host.rowconfigure(0, weight=1)
        scroll_host.columnconfigure(0, weight=1)

        _BG_HEADER = "#d0d0d0"
        _BG_ODD    = "#ffffff"
        _BG_EVEN   = "#f2f2f2"
        _BG_SEP    = "#c8c8c8"

        canvas = tk.Canvas(scroll_host, highlightthickness=0, bg=_BG_ODD)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(scroll_host, orient="vertical", command=canvas.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=vsb.set)

        # _BG_SEP as frame bg bleeds through padx/pady gaps → acts as separator lines
        grid_frame = tk.Frame(canvas, bg=_BG_SEP)
        canvas_window = canvas.create_window((0, 0), window=grid_frame, anchor="nw")

        def _on_grid_config(_e=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            try:
                bbox = canvas.bbox("all")
                if bbox is not None:
                    canvas.configure(width=bbox[2] - bbox[0])
            except tk.TclError:
                pass

        grid_frame.bind("<Configure>", _on_grid_config)

        scroll_host.columnconfigure(0, weight=0)

        def _mw(_e):
            canvas.yview_scroll(int(-1 * (_e.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _mw)
        grid_frame.bind("<MouseWheel>", _mw)

        # Header row
        for col, (text, w) in enumerate([("NPS", 10), ("DN", 10), ("Use", 6)]):
            tk.Label(
                grid_frame, text=text, width=w, anchor="center",
                font=("", 9, "bold"), bg=_BG_HEADER, pady=5,
            ).grid(row=0, column=col, sticky="nsew",
                   padx=(0, 1) if col < 2 else 0, pady=(0, 1))

        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)
        grid_frame.columnconfigure(2, weight=0)

        pairs = config.load_nps_dn_pairs()
        nps_active = set(self._global_settings.size_selection.nps)
        dn_active = set(self._global_settings.size_selection.dn)

        self._size_sel_pairs: list[dict[str, str]] = pairs
        self._size_sel_vars: list[tk.BooleanVar] = []

        for idx, pair in enumerate(pairs):
            nps = (pair.get("nps") or "-").strip() or "-"
            dn = (pair.get("dn") or "-").strip() or "-"
            checked = (nps != "-" and nps in nps_active) or (dn != "-" and dn in dn_active)
            var = tk.BooleanVar(value=checked)
            self._size_sel_vars.append(var)

            bg = _BG_ODD if idx % 2 == 0 else _BG_EVEN
            r = idx + 1

            tk.Label(grid_frame, text=nps, width=10, anchor="e", bg=bg, padx=8, pady=3).grid(
                row=r, column=0, sticky="nsew", padx=(0, 1), pady=(0, 1)
            )
            tk.Label(grid_frame, text=dn, width=10, anchor="e", bg=bg, padx=8, pady=3).grid(
                row=r, column=1, sticky="nsew", padx=(0, 1), pady=(0, 1)
            )
            cb_frame = tk.Frame(grid_frame, bg=bg)
            cb_frame.grid(row=r, column=2, sticky="nsew", pady=(0, 1))
            tk.Checkbutton(
                cb_frame, variable=var, bg=bg, activebackground=bg, relief="flat"
            ).pack(anchor="center", pady=1)

    def _set_all_size_selection(self, value: bool) -> None:
        for v in getattr(self, "_size_sel_vars", []):
            v.set(value)

    def _reset_size_selection_to_preferred(self) -> None:
        nps_pref = set(config.catalog_nps_preferred())
        dn_pref = set(config.catalog_dn_preferred())
        for pair, var in zip(self._size_sel_pairs, self._size_sel_vars):
            nps = (pair.get("nps") or "-").strip() or "-"
            dn = (pair.get("dn") or "-").strip() or "-"
            checked = (nps in nps_pref) or (dn in dn_pref)
            var.set(checked)

    def _collect_size_selection_from_ui(self) -> SizeSelection:
        nps_out: list[str] = []
        dn_out: list[str] = []
        for pair, var in zip(self._size_sel_pairs, self._size_sel_vars):
            if not var.get():
                continue
            nps = (pair.get("nps") or "-").strip() or "-"
            dn = (pair.get("dn") or "-").strip() or "-"
            if nps != "-":
                nps_out.append(nps)
            if dn != "-":
                dn_out.append(dn)
        return SizeSelection(nps=nps_out, dn=dn_out)

    def _save_size_selection(self) -> None:
        """현재 체크 상태를 Global Settings 에 반영. 사용 중인 사이즈를 해제하면 차단."""
        idx = self._current_class_idx()
        if idx is not None:
            self._save_class_row_at_index(idx)
        new_sel = self._collect_size_selection_from_ui()
        violations = self._size_selection_violations(new_sel)
        if violations:
            messagebox.showerror(
                "Cannot save Size Selection",
                "The following Size_From / Size_To values are still in use but would be removed:\n\n"
                + "\n".join(violations)
                + "\n\nRe-check those sizes, or remove them from the listed locations first.",
                parent=self,
            )
            return
        self._global_settings.size_selection = new_sel
        self._bundle.global_settings = copy.deepcopy(self._global_settings)
        self._refresh_size_dropdowns_after_selection_change()
        messagebox.showinfo(
            "Size Selection saved",
            "Global Size Selection updated. "
            "Class_Define / Reducing / Branch table dropdowns now reflect the new list.",
            parent=self,
        )

    def _size_selection_violations(self, new_sel: SizeSelection) -> list[str]:
        """new_sel 적용 시 어디에서 사용 중인 사이즈가 빠지는지 위반 메시지 목록."""
        out: list[str] = []
        new_nps = set(new_sel.nps)
        new_dn = set(new_sel.dn)

        def _allowed(mode: str) -> set[str]:
            return new_dn if (mode or "").strip().upper() == "DN" else new_nps

        for i, row in enumerate(self._bundle.class_define_rows):
            cn = (row.get("Class_Name") or "").strip() or f"(unnamed #{i+1})"
            mode = (row.get("Nominal_Size_System") or "NPS").strip() or "NPS"
            allowed = _allowed(mode)
            for col in ("Size_From", "Size_To"):
                val = (row.get(col) or "").strip()
                if val and val not in allowed:
                    out.append(f"Class {cn!r}: {col} {val!r} ({mode})")

        for tbl in self._bundle.reducing_tables:
            mode = (tbl.nominal_mode or "NPS").strip() or "NPS"
            allowed = _allowed(mode)
            for col, val in (("Size_From", tbl.size_from), ("Size_To", tbl.size_to)):
                v = (val or "").strip()
                if v and v not in allowed:
                    out.append(f"Reducing_Table {tbl.table_code!r}: {col} {v!r} ({mode})")
        for tbl in self._bundle.branch_tables:
            mode = (tbl.nominal_mode or "NPS").strip() or "NPS"
            allowed = _allowed(mode)
            for col, val in (("Size_From", tbl.size_from), ("Size_To", tbl.size_to)):
                v = (val or "").strip()
                if v and v not in allowed:
                    out.append(f"Branch_Table {tbl.table_code!r}: {col} {v!r} ({mode})")
        return out

    def _refresh_size_dropdowns_after_selection_change(self) -> None:
        """Size Selection 저장 후 Class detail 의 Size_From/To 드롭다운 값 재설정."""
        for h in ("Size_From", "Size_To"):
            cb = self._class_combos.get(h)
            if cb is not None:
                idx = self._current_class_idx()
                mode = "NPS"
                if idx is not None and 0 <= idx < len(self._bundle.class_define_rows):
                    mode = normalize_nominal_mode(
                        self._bundle.class_define_rows[idx].get("Nominal_Size_System")
                    )
                cb["values"] = ["", *self._selected_sizes_for_mode(mode)]

    def _refresh_design_unit_options(self, *, preserve_selection: bool) -> None:
        """선택된 Unit System 에 맞춰 Design Temperature 라벨 / Pressure Combobox values 재설정."""
        system = (self._unit_system_var.get() or "").strip()
        block = config.design_units_for(system) if system else {}
        temp_block = block.get("temperature") if isinstance(block, dict) else None
        press_block = block.get("pressure") if isinstance(block, dict) else None
        temp_allowed = list(temp_block.get("allowed", []) if isinstance(temp_block, dict) else [])
        press_allowed = list(press_block.get("allowed", []) if isinstance(press_block, dict) else [])
        temp_default = str(temp_block.get("default", "") if isinstance(temp_block, dict) else "")
        press_default = str(press_block.get("default", "") if isinstance(press_block, dict) else "")

        self._design_press_combo["values"] = ["", *press_allowed]

        if preserve_selection:
            cur_t = self._global_settings.design_temperature_unit
            cur_p = self._global_settings.design_pressure_unit
        else:
            cur_t = temp_default
            cur_p = press_default
        if cur_t not in temp_allowed:
            cur_t = temp_default if temp_default in temp_allowed else (temp_allowed[0] if temp_allowed else "")
        if cur_p not in press_allowed:
            cur_p = press_default if press_default in press_allowed else (press_allowed[0] if press_allowed else "")
        self._design_temp_var.set(cur_t)
        self._design_press_combo.set(cur_p)

    def _apply_global_settings_change(self) -> None:
        """현재 선택값을 _global_settings 에 반영하고 헤더/디테일을 재구성."""
        new_system = (self._unit_system_var.get() or "").strip()
        new_temp = (self._design_temp_var.get() or "").strip()
        new_press = (self._design_press_combo.get() or "").strip()

        self._save_class_detail_to_row()
        self._global_settings = ClassTemplateGlobalSettings(
            unit_system=new_system,
            design_temperature_unit=new_temp,
            design_pressure_unit=new_press,
            size_selection=copy.deepcopy(self._global_settings.size_selection),
        )
        self._refresh_derived_from_global_settings()
        self._rebuild_class_detail_widgets()
        self._refresh_class_listbox()
        if self._bundle.class_define_rows:
            self._class_list.selection_clear(0, "end")
            idx = self._last_shown_class_idx if self._last_shown_class_idx is not None else 0
            idx = max(0, min(idx, len(self._bundle.class_define_rows) - 1))
            self._class_list.selection_set(idx)
            self._load_class_detail()

    def _on_unit_system_changed(self) -> None:
        self._refresh_design_unit_options(preserve_selection=False)
        self._apply_global_settings_change()

    def _on_design_units_changed(self) -> None:
        self._apply_global_settings_change()

    def _tab_class(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb)
        nb.add(tab, text="Class_Define")

        lf = ttk.Frame(tab)
        lf.pack(side="left", fill="y", padx=4, pady=4, anchor="n")
        ttk.Label(lf, text="Class rows").pack(anchor="w")
        self._class_list_shell = tk.Frame(
            lf,
            highlightthickness=1,
            highlightbackground="#b0b0b0",
            highlightcolor="#b0b0b0",
            bg="#fafafa",
        )
        self._class_list_holder = tk.Frame(self._class_list_shell, bg="#fafafa")
        self._class_list_vsb = ttk.Scrollbar(self._class_list_holder, orient="vertical")
        self._class_list = tk.Listbox(
            self._class_list_holder,
            width=28,
            height=20,
            exportselection=False,
            relief="flat",
            bd=0,
            highlightthickness=0,
            bg=_STRIPE_A,
            selectbackground="#2b6cb0",
            selectforeground="white",
            activestyle="none",
            yscrollcommand=self._class_list_vsb.set,
        )
        self._class_list_vsb.config(command=self._class_list.yview)
        self._class_list.pack(side="left", fill="y", padx=(1, 0), pady=1)
        self._class_list_vsb.pack(side="left", fill="y", padx=(0, 1), pady=1)
        self._class_list_ph = _canvas_dashed_empty_state(
            self._class_list_shell,
            'No class rows yet. Use "Add row".',
            height=160,
            bg="#fafafa",
        )
        self._class_list_shell.pack(anchor="w")
        self._class_list.bind("<<ListboxSelect>>", lambda _e: self._load_class_detail())
        _bind_listbox_stripes_and_hover(self._class_list)
        bf = ttk.Frame(lf)
        bf.pack(fill="x", pady=4)
        ttk.Button(bf, text="Add row", command=self._add_class_row).pack(fill="x", pady=2)
        ttk.Button(bf, text="Delete row", command=self._del_class_row).pack(fill="x", pady=2)

        self._class_rf = ttk.LabelFrame(tab, text="Selected row")
        self._class_rf.pack(side="left", fill="y", padx=8, pady=4, anchor="n")
        self._class_entries: dict[str, tk.StringVar] = {}
        self._class_combos: dict[str, ttk.Combobox] = {}
        self._class_rows_frame: ttk.Frame | None = None
        self._rebuild_class_detail_widgets()

        self._refresh_class_listbox()
        if self._bundle.class_define_rows:
            self._class_list.selection_set(0)
            self._class_list.activate(0)
            self._class_list.see(0)
            self._class_list.focus_set()
            self._load_class_detail()

    def _rebuild_class_detail_widgets(self) -> None:
        """현재 헤더(`_class_define_headers`) 기준으로 Selected row 디테일 위젯을 재구성."""
        if not hasattr(self, "_class_rf"):
            return
        if self._class_rows_frame is not None:
            try:
                self._class_rows_frame.destroy()
            except tk.TclError:
                pass
        self._class_entries = {}
        self._class_combos = {}
        self._class_entry_widgets: dict[str, ttk.Entry] = {}
        self._schedule_edit_button: ttk.Button | None = None
        self._class_combo_warn_labels: dict[str, ttk.Label] = {}
        rows_f = ttk.Frame(self._class_rf)
        rows_f.pack(fill="both", expand=True)
        self._class_rows_frame = rows_f

        pair_skip: set[str] = {"Size_To"}
        if self._use_combined_temperature_pressure_rows():
            pair_skip.add(self._class_temp_to_h)
            pair_skip.add(self._class_press_to_h)

        lw = _CLASS_DETAIL_LABEL_WIDTH
        px = _CLASS_DETAIL_VALUE_PADX
        grid_row = 0
        for h in self._class_define_headers:
            if h in pair_skip:
                continue

            if self._use_combined_temperature_pressure_rows() and h == self._class_temp_from_h:
                lf_t = ttk.Frame(rows_f)
                lf_t.grid(row=grid_row, column=0, sticky="w", pady=1)
                ttk.Label(
                    lf_t,
                    text=bracket_unit_header("Design Temperature", self._class_design_temp_u),
                    width=lw,
                    anchor="w",
                ).pack(side="left")
                sub = ttk.Frame(rows_f)
                sub.grid(row=grid_row, column=1, sticky="w", pady=1, padx=px)
                v_tf = tk.StringVar()
                v_tt = tk.StringVar()
                self._class_entries[self._class_temp_from_h] = v_tf
                self._class_entries[self._class_temp_to_h] = v_tt
                temp_vcmd = (self.register(_is_signed_decimal_proposal), "%P")
                e_tf = ttk.Entry(
                    sub, textvariable=v_tf, width=18,
                    validate="key", validatecommand=temp_vcmd,
                )
                ttk.Label(sub, text="~").grid(row=0, column=1, padx=6)
                e_tt = ttk.Entry(
                    sub, textvariable=v_tt, width=18,
                    validate="key", validatecommand=temp_vcmd,
                )
                e_tf.grid(row=0, column=0, sticky="w")
                e_tt.grid(row=0, column=2, sticky="w")
                self._class_entry_widgets[self._class_temp_from_h] = e_tf
                self._class_entry_widgets[self._class_temp_to_h] = e_tt
                e_tf.bind(
                    "<FocusOut>",
                    lambda _e, h=self._class_temp_from_h: self._on_class_define_decimal_focus_out(h),
                )
                e_tt.bind(
                    "<FocusOut>",
                    lambda _e, h=self._class_temp_to_h: self._on_class_define_decimal_focus_out(h),
                )
                v_tf.trace_add("write", lambda *_a: self._refresh_class_define_pair_warnings())
                v_tt.trace_add("write", lambda *_a: self._refresh_class_define_pair_warnings())
                grid_row += 1
                continue

            if self._use_combined_temperature_pressure_rows() and h == self._class_press_from_h:
                lf_p = ttk.Frame(rows_f)
                lf_p.grid(row=grid_row, column=0, sticky="w", pady=1)
                ttk.Label(
                    lf_p,
                    text=bracket_unit_header("Design Pressure", self._class_design_press_u),
                    width=lw,
                    anchor="w",
                ).pack(side="left")
                subp = ttk.Frame(rows_f)
                subp.grid(row=grid_row, column=1, sticky="w", pady=1, padx=px)
                v_pf = tk.StringVar()
                v_pt = tk.StringVar()
                self._class_entries[self._class_press_from_h] = v_pf
                self._class_entries[self._class_press_to_h] = v_pt
                press_vcmd = (self.register(_is_signed_decimal_proposal), "%P")
                e_pf = ttk.Entry(
                    subp, textvariable=v_pf, width=18,
                    validate="key", validatecommand=press_vcmd,
                )
                ttk.Label(subp, text="~").grid(row=0, column=1, padx=6)
                e_pt = ttk.Entry(
                    subp, textvariable=v_pt, width=18,
                    validate="key", validatecommand=press_vcmd,
                )
                e_pf.grid(row=0, column=0, sticky="w")
                e_pt.grid(row=0, column=2, sticky="w")
                self._class_entry_widgets[self._class_press_from_h] = e_pf
                self._class_entry_widgets[self._class_press_to_h] = e_pt
                e_pf.bind(
                    "<FocusOut>",
                    lambda _e, h=self._class_press_from_h: self._on_class_define_decimal_focus_out(h),
                )
                e_pt.bind(
                    "<FocusOut>",
                    lambda _e, h=self._class_press_to_h: self._on_class_define_decimal_focus_out(h),
                )
                v_pf.trace_add("write", lambda *_a: self._refresh_class_define_pair_warnings())
                v_pt.trace_add("write", lambda *_a: self._refresh_class_define_pair_warnings())
                grid_row += 1
                continue

            if h == "Size_From":
                ttk.Label(rows_f, text="Size Range", width=lw).grid(
                    row=grid_row, column=0, sticky="w", pady=1
                )
                sub_s = ttk.Frame(rows_f)
                sub_s.grid(row=grid_row, column=1, sticky="w", pady=1, padx=px)
                cb_sf = ttk.Combobox(sub_s, width=18, state="readonly", values=[""])
                ttk.Label(sub_s, text="~").grid(row=0, column=1, padx=6)
                cb_st = ttk.Combobox(sub_s, width=18, state="readonly", values=[""])
                cb_sf.grid(row=0, column=0, sticky="w")
                cb_st.grid(row=0, column=2, sticky="w")
                cb_sf.bind("<<ComboboxSelected>>", lambda _e: self._on_size_range_selected("Size_From"))
                cb_st.bind("<<ComboboxSelected>>", lambda _e: self._on_size_range_selected("Size_To"))
                self._class_combos["Size_From"] = cb_sf
                self._class_combos["Size_To"] = cb_st
                grid_row += 1
                continue

            if h == _CORROSION_ALLOWANCE_KEY:
                ca_label = bracket_unit_header("Corrosion_Allowance", self._corrosion_unit_symbol)
                ttk.Label(rows_f, text=ca_label, width=lw).grid(row=grid_row, column=0, sticky="w", pady=1)
                ca_vcmd = (self.register(_is_unsigned_decimal_proposal), "%P")
                cb = ttk.Combobox(
                    rows_f,
                    width=42,
                    state="normal",
                    values=self._corrosion_combo_values,
                    validate="key",
                    validatecommand=ca_vcmd,
                )
                cb.grid(row=grid_row, column=1, sticky="w", pady=1, padx=px)
                self._class_combos[h] = cb
                cb.bind("<FocusOut>", lambda _e: self._on_corrosion_allowance_focus_out())
                grid_row += 1
                ttk.Label(rows_f, text="Schedule", width=lw).grid(
                    row=grid_row, column=0, sticky="w", pady=1
                )
                sched_btn = ttk.Button(
                    rows_f,
                    text="Edit Schedule...",
                    command=self._open_schedule_editor_for_selected_class,
                )
                sched_btn.grid(row=grid_row, column=1, sticky="w", pady=1, padx=px)
                self._schedule_edit_button = sched_btn
                grid_row += 1
                continue
            if h in ("Branch_Table_1", "Branch_Table_2", "Reducing_Table_1", "Reducing_Table_2"):
                lbl_frame = ttk.Frame(rows_f)
                lbl_frame.grid(row=grid_row, column=0, sticky="w", pady=1)
                ttk.Label(lbl_frame, text=h).pack(side="left")
                warn_lbl = ttk.Label(lbl_frame, text="⚠ mode mismatch", foreground="#b71c1c")
                cb = ttk.Combobox(rows_f, width=42, state="readonly", values=[""])
                cb.grid(row=grid_row, column=1, sticky="w", pady=1, padx=px)
                cb.bind(
                    "<<ComboboxSelected>>",
                    lambda _e, key=h: self._on_class_table_ref_selected(key),
                )
                self._class_combos[h] = cb
                self._class_combo_warn_labels[h] = warn_lbl
                grid_row += 1
                continue
            ttk.Label(rows_f, text=h, width=lw).grid(row=grid_row, column=0, sticky="w", pady=1)
            if h == "Design_Code":
                cb = ttk.Combobox(
                    rows_f,
                    width=42,
                    state="readonly",
                    values=list(self._design_code_options),
                )
                cb.grid(row=grid_row, column=1, sticky="w", pady=1, padx=px)
                self._class_combos[h] = cb
            elif h == "Nominal_Size_System":
                cb = ttk.Combobox(
                    rows_f,
                    width=42,
                    state="readonly",
                    values=list(self._nominal_size_options),
                )
                cb.grid(row=grid_row, column=1, sticky="w", pady=1, padx=px)
                cb.bind(
                    "<<ComboboxSelected>>",
                    lambda _e: self._on_nominal_size_system_changed(),
                )
                self._class_combos[h] = cb
            elif h == "Class_Base_Material":
                cb = ttk.Combobox(
                    rows_f,
                    width=42,
                    state="readonly",
                    values=self._material_combo_values,
                )
                cb.grid(row=grid_row, column=1, sticky="w", pady=1, padx=px)
                self._class_combos[h] = cb
            elif h == "Class_Rating":
                cb = ttk.Combobox(
                    rows_f,
                    width=42,
                    state="readonly",
                    values=self._rating_combo_values,
                )
                cb.grid(row=grid_row, column=1, sticky="w", pady=1, padx=px)
                self._class_combos[h] = cb
            else:
                v = tk.StringVar()
                e = ttk.Entry(rows_f, textvariable=v, width=44)
                e.grid(row=grid_row, column=1, sticky="w", pady=1, padx=px)
                self._class_entries[h] = v
                self._class_entry_widgets[h] = e
                if h == "Class_Name":
                    e.bind("<FocusOut>", self._on_class_name_focus_out, add="+")
                    e.bind("<KeyRelease>", lambda _e: self._refresh_class_name_gate(), add="+")
                elif h == "Revision_No":
                    e.bind("<FocusOut>", self._on_revision_no_focus_out, add="+")
            grid_row += 1
        rows_f.columnconfigure(1, weight=0)
        self._refresh_class_name_gate()

    def _on_nominal_size_system_changed(self) -> None:
        """선택된 Class 의 Nominal_Size_System 이 바뀌면 Size_From/Size_To 드롭다운 후보를 갱신.

        새 모드에서 사용할 수 없는 기존 Size_From/Size_To 값은 비운다.
        """
        idx = self._current_class_idx()
        if idx is None:
            return
        ns_cb = self._class_combos.get("Nominal_Size_System")
        if ns_cb is None:
            return
        new_mode = normalize_nominal_mode(ns_cb.get())
        sizes = self._selected_sizes_for_mode(new_mode)
        sizes_set = set(sizes)
        for h in ("Size_From", "Size_To"):
            cb = self._class_combos.get(h)
            if cb is None:
                continue
            cur = cb.get()
            cb["values"] = ["", *sizes]
            if cur and cur not in sizes_set:
                cb.set("")
        for h in ("Reducing_Table_1", "Reducing_Table_2"):
            cb = self._class_combos.get(h)
            if cb is not None:
                cb["values"] = list(self._reducing_names_for_mode(new_mode))
        for h in ("Branch_Table_1", "Branch_Table_2"):
            cb = self._class_combos.get(h)
            if cb is not None:
                cb["values"] = list(self._branch_names_for_mode(new_mode))
        self._save_class_detail_to_row()
        self._refresh_class_name_gate()
        self._refresh_class_table_warnings()

    def _refresh_combo_lists(self) -> None:
        idx = self._current_class_idx()
        mode = "NPS"
        if idx is not None and 0 <= idx < len(self._bundle.class_define_rows):
            mode = normalize_nominal_mode(
                self._bundle.class_define_rows[idx].get("Nominal_Size_System")
            )
        rvals = list(self._reducing_names_for_mode(mode))
        bvals = list(self._branch_names_for_mode(mode))
        size_vals = ["", *self._selected_sizes_for_mode(mode)]
        for h, widget in self._class_combos.items():
            if h in ("Branch_Table_1", "Branch_Table_2"):
                widget["values"] = bvals
            elif h in ("Reducing_Table_1", "Reducing_Table_2"):
                widget["values"] = rvals
            elif h in ("Size_From", "Size_To"):
                widget["values"] = size_vals

    def _refresh_class_listbox(self) -> None:
        self._class_list.delete(0, "end")
        for row in self._bundle.class_define_rows:
            cn = (row.get("Class_Name") or "").strip() or "undefined"
            self._class_list.insert("end", cn)
        if self._bundle.class_define_rows:
            self._class_list_ph.pack_forget()
            self._class_list_holder.pack(anchor="w")
        else:
            self._class_list_holder.pack_forget()
            self._class_list_ph.pack(anchor="w")
        _listbox_apply_stripes(self._class_list)
        self._refresh_components_class_list()

    def _current_class_idx(self) -> int | None:
        sel = self._class_list.curselection()
        if not sel:
            return None
        return int(sel[0])

    def _save_class_row_at_index(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._bundle.class_define_rows):
            return
        row = self._bundle.class_define_rows[idx]
        for h, v in self._class_entries.items():
            row[h] = v.get() or ""
        for h, cb in self._class_combos.items():
            row[h] = cb.get() or ""

    def _save_class_detail_to_row(self) -> None:
        idx = self._current_class_idx()
        if idx is None:
            return
        self._save_class_row_at_index(idx)

    def _on_class_define_decimal_focus_out(self, header: str) -> None:
        """Temp/Press From·To 필드 FocusOut: 표기 정규화 후 페어 워닝 갱신."""
        var = self._class_entries.get(header)
        if var is None:
            return
        raw = var.get()
        normalized = _normalize_decimal_string(raw)
        if normalized != raw:
            var.set(normalized)
        self._refresh_class_define_pair_warnings()

    def _on_corrosion_allowance_focus_out(self) -> None:
        """Corrosion Allowance Combobox FocusOut: 표기 정규화."""
        cb = self._class_combos.get(_CORROSION_ALLOWANCE_KEY)
        if cb is None:
            return
        raw = cb.get()
        normalized = _normalize_decimal_string(raw)
        if normalized != raw:
            cb.set(normalized)

    def _refresh_class_define_pair_warnings(self) -> None:
        """Design_Temperature / Design_Pressure 의 From > To 시 To 필드를 빨갛게 표시."""
        widgets = getattr(self, "_class_entry_widgets", None)
        entries = getattr(self, "_class_entries", None)
        if not widgets or not entries:
            return
        for from_h, to_h in (
            (self._class_temp_from_h, self._class_temp_to_h),
            (self._class_press_from_h, self._class_press_to_h),
        ):
            if not (from_h and to_h):
                continue
            from_var = entries.get(from_h)
            to_var = entries.get(to_h)
            to_widget = widgets.get(to_h)
            if from_var is None or to_var is None or to_widget is None:
                continue
            fv = _parse_signed_decimal(from_var.get())
            tv = _parse_signed_decimal(to_var.get())
            invalid = fv is not None and tv is not None and fv > tv
            try:
                to_widget.configure(style="Invalid.TEntry" if invalid else "TEntry")
            except tk.TclError:
                pass

    def _on_tab_changed(self) -> None:
        """탭 전환 시 Class_Define 폼을 bundle에 flush."""
        self._save_class_detail_to_row()

    def _load_class_detail(self) -> None:
        idx = self._current_class_idx()
        if idx is None:
            return
        if (
            self._last_shown_class_idx is not None
            and self._last_shown_class_idx != idx
        ):
            self._save_class_row_at_index(self._last_shown_class_idx)
        row = self._bundle.class_define_rows[idx]
        self._refresh_combo_lists()
        for h, v in self._class_entries.items():
            v.set(row.get(h, ""))
        for h, cb in self._class_combos.items():
            cb.set(row.get(h, ""))
        self._last_shown_class_idx = idx
        self._refresh_class_name_gate()
        self._refresh_class_table_warnings()
        self._refresh_class_define_pair_warnings()

    def _on_class_table_ref_selected(self, key: str) -> None:
        """사용자가 Reducing/Branch table combo 에서 값을 고른 직후 호출."""
        self._save_class_detail_to_row()
        self._refresh_class_table_warnings()

    def _refresh_class_table_warnings(self) -> None:
        """현재 Class 의 Nominal_Size_System 대비, 참조된 Reducing/Branch table 의 nominal mode 불일치 시각 표시."""
        warn_labels = getattr(self, "_class_combo_warn_labels", {})
        if not warn_labels:
            return
        idx = self._current_class_idx()
        if idx is None:
            for h in warn_labels:
                cb = self._class_combos.get(h)
                if cb is not None:
                    cb.configure(style="TCombobox")
                lbl = warn_labels[h]
                if lbl.winfo_ismapped():
                    lbl.pack_forget()
            return
        row = self._bundle.class_define_rows[idx]
        class_mode = normalize_nominal_mode(row.get("Nominal_Size_System"))
        reducing_modes = {
            t.table_code.strip(): normalize_nominal_mode(t.nominal_mode)
            for t in self._bundle.reducing_tables
            if t.table_code.strip()
        }
        branch_modes = {
            t.table_code.strip(): normalize_nominal_mode(t.nominal_mode)
            for t in self._bundle.branch_tables
            if t.table_code.strip()
        }
        for h, lbl in warn_labels.items():
            cb = self._class_combos.get(h)
            if cb is None:
                continue
            val = cb.get().strip()
            mismatch = False
            if val:
                if h in ("Reducing_Table_1", "Reducing_Table_2"):
                    mismatch = val in reducing_modes and reducing_modes[val] != class_mode
                elif h in ("Branch_Table_1", "Branch_Table_2"):
                    mismatch = val in branch_modes and branch_modes[val] != class_mode
            if mismatch:
                cb.configure(style="Warn.TCombobox")
                if not lbl.winfo_ismapped():
                    lbl.pack(side="left", padx=(4, 0))
            else:
                cb.configure(style="TCombobox")
                if lbl.winfo_ismapped():
                    lbl.pack_forget()

    def _add_class_row(self) -> None:
        self._save_class_detail_to_row()
        nr = self._new_class_row()
        self._bundle.class_define_rows.append(nr)
        self._refresh_class_listbox()
        self._class_list.selection_clear(0, "end")
        self._class_list.selection_set(len(self._bundle.class_define_rows) - 1)
        self._load_class_detail()

    def _del_class_row(self) -> None:
        idx = self._current_class_idx()
        if idx is None:
            return
        if len(self._bundle.class_define_rows) <= 1:
            messagebox.showinfo("Delete", "At least one class row is required.", parent=self)
            return
        if messagebox.askyesno("Delete", "Delete this class row?", parent=self):
            self._bundle.class_define_rows.pop(idx)
            self._last_shown_class_idx = None
            self._refresh_class_listbox()
            self._class_list.selection_set(min(idx, len(self._bundle.class_define_rows) - 1))
            self._load_class_detail()

    def _open_schedule_editor_for_selected_class(self) -> None:
        """현재 선택된 Class 의 (Size_From, Size_To, Schedule) 행을 편집하는 모달 팝업.

        OK 시 `self._bundle.schedule_rows` 의 해당 Class 행들을 로컬 편집본으로 교체.
        Cancel / 창 닫기 시 변경 사항 폐기.
        """
        idx = self._current_class_idx()
        if idx is None:
            return
        self._save_class_detail_to_row()
        class_row = self._bundle.class_define_rows[idx]
        class_name = str(class_row.get("Class_Name", "") or "").strip()
        if not class_name:
            return

        active_sizes_guard = list(self._active_sizes_for_class(class_name))
        if not active_sizes_guard:
            messagebox.showwarning(
                "Class not ready",
                f"Class '{class_name}'의 Active Sizes를 결정할 수 없습니다.\n"
                "Class_Define에서 Size_From / Size_To를 먼저 설정한 뒤 Schedule을 편집해 주세요.",
                parent=self,
            )
            return

        local_rows: list[dict[str, str]] = []
        for r in self._bundle.schedule_rows:
            if str(r.get("Class_Name", "") or "").strip() == class_name:
                local_rows.append(
                    {
                        "Class_Name": class_name,
                        "Size_From": str(r.get("Size_From", "") or ""),
                        "Size_To": str(r.get("Size_To", "") or ""),
                        "Schedule": str(r.get("Schedule", "") or ""),
                    }
                )

        win = tk.Toplevel(self)
        win.title(f"Schedule — {class_name}")
        win.transient(self)
        win.resizable(True, True)
        try:
            win.geometry("620x480")
        except tk.TclError:
            pass

        outer = ttk.Frame(win)
        outer.pack(fill="both", expand=True, padx=8, pady=8)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        cols = ("Size_From", "Size_To", "Schedule")
        schedule_values = scheduleAllowlist()
        schedule_value_set = set(schedule_values)
        sz_vals = list(self._active_sizes_for_class(class_name))
        sz_vals_set = set(sz_vals)
        sz_vals_by_float: dict[float, str] = {}
        for _s in sz_vals:
            try:
                sz_vals_by_float[float(_s)] = _s
            except ValueError:
                pass
        tree_holder = ttk.Frame(outer)
        tree_holder.grid(row=0, column=0, sticky="nsew")
        tree_holder.grid_rowconfigure(0, weight=1)
        tree_holder.grid_columnconfigure(0, weight=1)
        tree = ttk.Treeview(
            tree_holder,
            columns=cols,
            show="headings",
            height=14,
            style="WizardSchedule.Treeview",
        )
        tree.heading("Size_From", text="Size_From", anchor="center")
        tree.heading("Size_To", text="Size_To", anchor="center")
        tree.heading("Schedule", text="Schedule", anchor="center")
        tree.column("Size_From", width=150, minwidth=130, anchor="center", stretch=False)
        tree.column("Size_To", width=150, minwidth=130, anchor="center", stretch=False)
        tree.column("Schedule", width=220, minwidth=180, anchor="center", stretch=True)
        sy = ttk.Scrollbar(tree_holder, orient="vertical", command=tree.yview)
        sx = ttk.Scrollbar(tree_holder, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        tree.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        _tree_setup_tags(tree)

        editor: dict[str, tk.Widget | None] = {"w": None}
        active_commit: dict[str, object] = {"fn": None}
        last_edit: dict[str, str] = {"iid": "", "col": "#1"}

        def _close_editor_now() -> None:
            fn = active_commit["fn"]
            if fn is not None:
                active_commit["fn"] = None
                try:
                    fn()  # type: ignore[operator]
                except Exception:
                    pass
            w = editor["w"]
            if w is not None:
                editor["w"] = None
                try:
                    w.destroy()
                except tk.TclError:
                    pass

        def _is_numeric_text(value: str) -> bool:
            raw = value.strip()
            if not raw:
                return True
            try:
                float(raw)
                return True
            except ValueError:
                return False

        def _parse_float_or_none(value: str) -> float | None:
            raw = str(value or "").strip()
            if not raw:
                return None
            try:
                return float(raw)
            except ValueError:
                return None

        def _validate_numeric_key(proposed: str) -> bool:
            if proposed == "":
                return True
            if proposed.count(".") > 1:
                return False
            return all(ch.isdigit() or ch == "." for ch in proposed)

        def refill_rows(select_iid: str | None = None) -> None:
            for iid in tree.get_children():
                tree.delete(iid)
            for vis_idx, row in enumerate(local_rows):
                iid = f"r{vis_idx}"
                sf = str(row.get("Size_From", "") or "")
                st = str(row.get("Size_To", "") or "")
                out_of_range = sz_vals_set and (
                    (sf.strip() and sf.strip() not in sz_vals_set)
                    or (st.strip() and st.strip() not in sz_vals_set)
                )
                base_tags = _tree_row_tags(vis_idx)
                tags = (*base_tags, "size_warn") if out_of_range else base_tags
                tree.insert(
                    "",
                    "end",
                    iid=iid,
                    values=(sf, st, row.get("Schedule", "")),
                    tags=tags,
                )
            kids = tree.get_children()
            if not kids:
                return
            target = kids[0]
            if select_iid is not None and tree.exists(select_iid):
                target = select_iid
            tree.selection_set(target)
            tree.focus(target)
            tree.see(target)

        def add_row_for_selected() -> bool:
            local_rows.append(
                {"Class_Name": class_name, "Size_From": "", "Size_To": "", "Schedule": ""}
            )
            new_iid = f"r{len(local_rows) - 1}"
            refill_rows(select_iid=new_iid)
            start_edit(new_iid, "#1", None)
            return True

        def delete_selected_row() -> bool:
            sel = tree.selection()
            if not sel:
                return False
            src_idx = int(str(sel[0])[1:])
            if 0 <= src_idx < len(local_rows):
                local_rows.pop(src_idx)
                refill_rows()
                return True
            return False

        def start_edit(iid: str, col_id: str, first_char: str | None = None) -> None:
            _close_editor_now()
            last_edit["iid"] = iid
            last_edit["col"] = col_id
            bbox = tree.bbox(iid, col_id)
            if not bbox:
                return
            x, y, w, h = bbox
            col_num = int(col_id[1:]) - 1
            current = tree.item(iid, "values")[col_num]
            if col_id == "#3":
                ent: tk.Widget = ttk.Combobox(tree, values=schedule_values, state="readonly")
            elif col_id in ("#1", "#2"):
                ent = ttk.Combobox(tree, values=sz_vals, state="normal")
            else:
                vcmd = (win.register(_validate_numeric_key), "%P")
                ent = tk.Entry(tree, validate="key", validatecommand=vcmd)
            ent.place(x=x, y=y, width=w, height=h)
            initial = first_char if first_char is not None else str(current)
            if col_id == "#3":
                schedule_initial = normalizeScheduleValue(initial)
                if schedule_initial in schedule_value_set:
                    ent.set(schedule_initial)
                elif str(current).strip():
                    ent.set(str(current).strip())
                else:
                    ent.set("")
            elif col_id in ("#1", "#2"):
                ent.set(initial)
            else:
                ent.insert(0, initial)
            ent.focus_set()
            if first_char is None:
                try:
                    ent.selection_range(0, tk.END)
                except (tk.TclError, AttributeError):
                    pass

            def _next_cell(current_iid: str, current_col_id: str, delta: int) -> tuple[str, str] | None:
                row_ids = list(tree.get_children())
                if current_iid not in row_ids:
                    return None
                col_ids = ["#1", "#2", "#3"]
                row_pos = row_ids.index(current_iid)
                col_pos = col_ids.index(current_col_id)
                next_pos = col_pos + delta
                next_row = row_pos
                if next_pos >= len(col_ids):
                    next_pos = 0
                    next_row += 1
                elif next_pos < 0:
                    next_pos = len(col_ids) - 1
                    next_row -= 1
                if not (0 <= next_row < len(row_ids)):
                    return None
                return row_ids[next_row], col_ids[next_pos]

            def do_commit(move_delta: int | None = None) -> bool:
                new_raw = ent.get().strip()
                new_value = new_raw
                if col_id in ("#1", "#2"):
                    try:
                        ent.configure(bg="white")
                    except tk.TclError:
                        pass
                if col_id in ("#1", "#2") and new_raw:
                    try:
                        as_float = float(new_raw)
                    except ValueError:
                        messagebox.showerror(
                            "Invalid size",
                            f"'{new_raw}' is not a valid size.\n"
                            f"Allowed: {', '.join(sz_vals)}",
                            parent=win,
                        )
                        ent.focus_set()
                        return False
                    canon = sz_vals_by_float.get(as_float)
                    if canon is None:
                        messagebox.showerror(
                            "Invalid size",
                            f"'{new_raw}' is not in this class's Active Sizes.\n"
                            f"Allowed: {', '.join(sz_vals)}",
                            parent=win,
                        )
                        ent.focus_set()
                        return False
                    new_value = canon
                if col_id == "#3":
                    normalized = normalizeScheduleValue(new_raw)
                    if normalized and normalized not in schedule_value_set:
                        messagebox.showerror(
                            "Invalid schedule",
                            "Schedule must be selected from the standard allowlist.",
                            parent=win,
                        )
                        ent.focus_set()
                        return False
                    new_value = normalized
                vals = list(tree.item(iid, "values"))
                vals[col_num] = new_value
                if col_id == "#2":
                    size_from_value = _parse_float_or_none(str(vals[0] or ""))
                    size_to_value = _parse_float_or_none(str(vals[1] or ""))
                    if size_from_value is not None and size_to_value is not None and size_to_value < size_from_value:
                        try:
                            ent.configure(bg="#ffd6d6")
                        except tk.TclError:
                            pass
                        try:
                            ent.focus_set()
                        except tk.TclError:
                            pass
                        return False
                tree.item(iid, values=tuple(vals))
                src_idx = int(iid[1:])
                if 0 <= src_idx < len(local_rows):
                    row = local_rows[src_idx]
                    row["Class_Name"] = class_name
                    row["Size_From"] = str(vals[0] or "")
                    row["Size_To"] = str(vals[1] or "")
                    row["Schedule"] = str(vals[2] or "")
                ent.destroy()
                editor["w"] = None
                if move_delta is not None:
                    next_cell = _next_cell(iid, col_id, move_delta)
                    if next_cell is not None:
                        start_edit(next_cell[0], next_cell[1], None)
                return True

            def commit(_e=None) -> str:
                do_commit(None)
                return "break"

            def cancel(_e=None) -> str:
                active_commit["fn"] = None
                editor["w"] = None
                try:
                    ent.destroy()
                except tk.TclError:
                    pass
                return "break"

            active_commit["fn"] = lambda: do_commit(None)

            ent.bind("<Escape>", cancel)
            ent.bind("<Tab>", lambda _e: "break" if do_commit(1) else "break")
            ent.bind("<Shift-Tab>", lambda _e: "break" if do_commit(-1) else "break")
            ent.bind("<ISO_Left_Tab>", lambda _e: "break" if do_commit(-1) else "break")

            if col_id in ("#1", "#2", "#3"):
                cb = ent

                def try_open_dropdown() -> bool:
                    try:
                        cb.tk.call("ttk::combobox::Post", cb)
                        return True
                    except tk.TclError:
                        try:
                            cb.event_generate("<Alt-Down>")
                            return True
                        except tk.TclError:
                            return False

                def is_dropdown_open() -> bool:
                    try:
                        popdown = cb.tk.call("ttk::combobox::PopdownWindow", cb)
                        return bool(int(cb.tk.call("winfo", "ismapped", popdown)))
                    except (tk.TclError, ValueError):
                        return False

                def close_dropdown_now() -> None:
                    try:
                        cb.tk.call("ttk::combobox::Unpost", cb)
                    except tk.TclError:
                        pass

                def on_up_or_down(_e=None) -> str | None:
                    if is_dropdown_open():
                        return None
                    try_open_dropdown()
                    return "break"

                def cb_tab(delta: int) -> str:
                    if is_dropdown_open():
                        close_dropdown_now()
                        cb.after(1, lambda: do_commit(delta))
                    else:
                        do_commit(delta)
                    return "break"

                def _cb_values_for_wheel() -> list[str]:
                    if col_id == "#3":
                        return list(schedule_values)
                    return list(sz_vals)

                def move_by_wheel(e: tk.Event) -> str:
                    values = _cb_values_for_wheel()
                    if not values:
                        return "break"
                    current = str(cb.get() or "").strip()
                    try:
                        idx = values.index(current)
                    except ValueError:
                        idx = 0
                    delta = getattr(e, "delta", 0)
                    if delta == 0 and hasattr(e, "num"):
                        if e.num == 4:
                            delta = 120
                        elif e.num == 5:
                            delta = -120
                    step = -1 if delta > 0 else 1
                    next_idx = max(0, min(len(values) - 1, idx + step))
                    cb.set(values[next_idx])
                    return "break"

                def consume_key(_e=None) -> str:
                    return "break"

                # Override Tab/Shift-Tab with combobox-aware versions.
                cb.bind("<Tab>", lambda _e: cb_tab(1))
                cb.bind("<Shift-Tab>", lambda _e: cb_tab(-1))
                cb.bind("<ISO_Left_Tab>", lambda _e: cb_tab(-1))
                cb.bind("<Return>", lambda _e: "break" if do_commit(1) else "break")
                cb.bind("<Down>", on_up_or_down)
                cb.bind("<KeyPress-Down>", on_up_or_down, add="+")
                cb.bind("<KP_Down>", on_up_or_down, add="+")
                cb.bind("<Up>", on_up_or_down)
                cb.bind("<KeyPress-Up>", on_up_or_down, add="+")
                cb.bind("<KP_Up>", on_up_or_down, add="+")
                if col_id == "#3":
                    cb.bind("<Left>", consume_key)
                    cb.bind("<Right>", consume_key)
                cb.bind("<MouseWheel>", move_by_wheel)
                cb.bind("<Button-4>", move_by_wheel)
                cb.bind("<Button-5>", move_by_wheel)
                # Item clicked in dropdown list → commit and move right.
                cb.bind("<<ComboboxSelected>>", lambda _e: "break" if do_commit(1) else "break")
            else:
                ent.bind("<Return>", commit)

            editor["w"] = ent

        def target_cell(event: tk.Event | None = None) -> tuple[str, str] | None:
            sel = tree.selection()
            if event is None:
                if not sel:
                    return None
                return str(sel[0]), "#1"
            row_iid = tree.identify_row(event.y)
            col_id = tree.identify_column(event.x)
            if not row_iid:
                if not sel:
                    return None
                row_iid = str(sel[0])
            if col_id not in ("#1", "#2", "#3"):
                col_id = "#1"
            return row_iid, col_id

        def on_double_click(e: tk.Event) -> None:
            tgt = target_cell(e)
            if tgt is None:
                return
            start_edit(tgt[0], tgt[1], None)

        def on_single_click(e: tk.Event) -> str | None:
            tgt = target_cell(e)
            if tgt is None:
                if editor["w"] is not None:
                    try:
                        editor["w"].event_generate("<Return>")
                    except tk.TclError:
                        pass
                return None
            row_iid, col_id = tgt
            def begin_edit_after_select() -> None:
                if not tree.exists(row_iid):
                    return
                tree.selection_set(row_iid)
                tree.focus(row_iid)
                tree.see(row_iid)
                start_edit(row_iid, col_id, None)

            win.after_idle(begin_edit_after_select)
            return None

        def on_return(_e: tk.Event) -> str:
            tgt = target_cell(None)
            if tgt is None:
                return "break"
            start_edit(tgt[0], tgt[1], None)
            return "break"

        def on_keypress(e: tk.Event) -> str | None:
            if editor["w"] is not None:
                # Keep tree navigation from stealing focus while editing.
                return "break"
            ch = e.char
            if ch and len(ch) == 1 and ch.isprintable() and not ch.isspace():
                tgt = target_cell(None)
                if tgt is None:
                    return "break"
                start_edit(tgt[0], tgt[1], ch)
                return "break"
            return None

        def on_tree_tab(delta: int) -> str:
            if editor["w"] is not None:
                return "break"
            iid = last_edit.get("iid", "")
            col = last_edit.get("col", "#1")
            if not iid or not tree.exists(iid):
                sel = tree.selection()
                if not sel:
                    return "break"
                iid = str(sel[0])
                col = "#1"
            col_ids = ["#1", "#2", "#3"]
            col_pos = col_ids.index(col) if col in col_ids else 0
            next_pos = col_pos + delta
            next_row_idx = col_ids.index(col) if col in col_ids else 0
            row_ids = list(tree.get_children())
            if iid not in row_ids:
                return "break"
            row_pos = row_ids.index(iid)
            next_pos = col_pos + delta
            next_row_pos = row_pos
            if next_pos >= len(col_ids):
                next_pos = 0
                next_row_pos += 1
            elif next_pos < 0:
                next_pos = len(col_ids) - 1
                next_row_pos -= 1
            if not (0 <= next_row_pos < len(row_ids)):
                return "break"
            next_iid = row_ids[next_row_pos]
            next_col = col_ids[next_pos]
            tree.selection_set(next_iid)
            tree.focus(next_iid)
            tree.see(next_iid)
            start_edit(next_iid, next_col, None)
            return "break"

        tree.bind("<Button-1>", on_single_click)
        tree.bind("<Double-1>", on_double_click)
        tree.bind("<Return>", on_return)
        tree.bind("<KeyPress>", on_keypress)
        tree.bind("<Tab>", lambda _e: on_tree_tab(1))
        tree.bind("<Shift-Tab>", lambda _e: on_tree_tab(-1))
        tree.bind("<ISO_Left_Tab>", lambda _e: on_tree_tab(-1))

        row_btns = ttk.Frame(outer)
        row_btns.grid(row=1, column=0, sticky="e", pady=(8, 0))
        ttk.Button(row_btns, text="Add row", command=add_row_for_selected).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(row_btns, text="Delete row", command=delete_selected_row).pack(
            side="left"
        )

        def _validate_coverage() -> list[str]:
            """active_sizes_guard 전체가 local_rows에 의해 빠짐없이 커버되고, 범위 밖/형식 오류가 없는지."""
            errs: list[str] = []
            size_index = {s: i for i, s in enumerate(active_sizes_guard)}
            covered: set[str] = set()
            for n, r in enumerate(local_rows, 1):
                sf = (r.get("Size_From") or "").strip()
                st = (r.get("Size_To") or "").strip()
                sched = (r.get("Schedule") or "").strip()
                if not sf or not st or not sched:
                    errs.append(f"Row {n}: Size_From / Size_To / Schedule을 모두 채워야 합니다.")
                    continue
                if sf not in size_index:
                    errs.append(f"Row {n}: Size_From '{sf}' 가 Class 의 Active Sizes 범위 밖입니다.")
                    continue
                if st not in size_index:
                    errs.append(f"Row {n}: Size_To '{st}' 가 Class 의 Active Sizes 범위 밖입니다.")
                    continue
                if size_index[sf] > size_index[st]:
                    errs.append(f"Row {n}: Size_From '{sf}' 가 Size_To '{st}' 보다 큽니다.")
                    continue
                for i in range(size_index[sf], size_index[st] + 1):
                    covered.add(active_sizes_guard[i])
            missing = [s for s in active_sizes_guard if s not in covered]
            if missing and not errs:
                errs.append(
                    "Schedule이 Class 의 모든 사이즈를 커버하지 않습니다.\n"
                    "누락된 사이즈: " + ", ".join(missing)
                )
            return errs

        def on_ok() -> None:
            _close_editor_now()
            errs = _validate_coverage()
            if errs:
                messagebox.showerror("Schedule incomplete", "\n".join(errs), parent=win)
                return
            self._bundle.schedule_rows = [
                r
                for r in self._bundle.schedule_rows
                if str(r.get("Class_Name", "") or "").strip() != class_name
            ]
            for r in local_rows:
                self._bundle.schedule_rows.append(
                    {
                        "Class_Name": class_name,
                        "Size_From": str(r.get("Size_From", "") or ""),
                        "Size_To": str(r.get("Size_To", "") or ""),
                        "Schedule": str(r.get("Schedule", "") or ""),
                    }
                )
            try:
                win.grab_release()
            except tk.TclError:
                pass
            win.destroy()

        def on_cancel() -> None:
            _close_editor_now()
            try:
                win.grab_release()
            except tk.TclError:
                pass
            win.destroy()

        bottom = ttk.Frame(outer)
        bottom.grid(row=2, column=0, sticky="e", pady=(8, 0))
        ttk.Button(bottom, text="OK", command=on_ok).pack(side="right", padx=6)
        ttk.Button(bottom, text="Cancel", command=on_cancel).pack(side="right", padx=6)

        win.protocol("WM_DELETE_WINDOW", on_cancel)

        refill_rows()
        try:
            win.grab_set()
        except tk.TclError:
            pass
        win.wait_window()

    def _current_nominal_mode_for_tables(self) -> str:
        """Reducing/Branch 테이블 편집 시 사용할 nominal mode — 현재 선택된 Class 기준, 없으면 NPS."""
        idx = self._current_class_idx()
        if idx is not None and 0 <= idx < len(self._bundle.class_define_rows):
            return normalize_nominal_mode(
                self._bundle.class_define_rows[idx].get("Nominal_Size_System")
            )
        for row in self._bundle.class_define_rows:
            mode = (row.get("Nominal_Size_System") or "").strip()
            if mode:
                return normalize_nominal_mode(mode)
        return "NPS"

    def _tab_reducing_tables(self, nb: ttk.Notebook) -> None:
        """Reducing tables 관리 탭 (sheet: Reducing_Table)."""
        tab = ttk.Frame(nb)
        nb.add(tab, text="Reducing Tables")

        def refresh_combos() -> None:
            self._refresh_combo_lists()
            self._load_class_detail()

        refill = _build_named_tables_panel(
            tab,
            self,
            self._bundle.reducing_tables,
            self._bundle,
            pair_kind="reducing",
            refresh_dropdowns=refresh_combos,
            nominal_mode_provider=self._current_nominal_mode_for_tables,
            size_selection_provider=lambda: self._global_settings.size_selection,
        )
        self._reducing_tab_refresh = refill

    def _tab_branch_tables(self, nb: ttk.Notebook) -> None:
        """Branch tables 관리 탭 (sheet: Branch_Table)."""
        tab = ttk.Frame(nb)
        nb.add(tab, text="Branch Tables")

        def refresh_combos() -> None:
            self._refresh_combo_lists()
            self._load_class_detail()

        refill = _build_named_tables_panel(
            tab,
            self,
            self._bundle.branch_tables,
            self._bundle,
            pair_kind="branch",
            refresh_dropdowns=refresh_combos,
            nominal_mode_provider=self._current_nominal_mode_for_tables,
            size_selection_provider=lambda: self._global_settings.size_selection,
        )
        self._branch_tab_refresh = refill

    def _tab_components(self, nb: ttk.Notebook) -> None:
        """Components 탭 — 좌측 Class 목록 + 선택 행 read-only status,
        우측 Group 선택 콤보 1개와 단일 Add/Edit/Delete + 단일 행 목록."""
        tab = ttk.Frame(nb)
        nb.add(tab, text="Components")

        self._comp_group_label_to_sheet = {
            _group_display_label(label): sn for sn, label, _ in COMPONENT_GROUPS
        }
        self._comp_current_group = COMPONENT_GROUPS[0][0]
        self._comp_item_map: dict[str, tuple[str, int]] = {}

        left = ttk.Frame(tab)
        left.pack(side="left", fill="y", padx=4, pady=4, anchor="n")
        ttk.Label(left, text="Class rows").pack(anchor="w")
        list_shell = tk.Frame(
            left,
            highlightthickness=1,
            highlightbackground="#b0b0b0",
            highlightcolor="#b0b0b0",
            bg="#fafafa",
        )
        list_shell.pack(anchor="w")
        list_holder = tk.Frame(list_shell, bg="#fafafa")
        list_holder.pack(anchor="w")
        list_vsb = ttk.Scrollbar(list_holder, orient="vertical")
        self._comp_class_list = tk.Listbox(
            list_holder,
            width=24,
            height=10,
            exportselection=False,
            relief="flat",
            bd=0,
            highlightthickness=0,
            bg=_STRIPE_A,
            selectbackground="#2b6cb0",
            selectforeground="white",
            activestyle="none",
            yscrollcommand=list_vsb.set,
        )
        list_vsb.config(command=self._comp_class_list.yview)
        self._comp_class_list.pack(side="left", fill="y", padx=(1, 0), pady=1)
        list_vsb.pack(side="left", fill="y", padx=(0, 1), pady=1)
        self._comp_class_list.bind(
            "<<ListboxSelect>>", lambda _e: self._on_components_class_selected()
        )
        _bind_listbox_stripes_and_hover(self._comp_class_list)

        # 선택한 component 행의 필드/값을 읽기 전용으로 보여주는 status 패널.
        ttk.Label(left, text="Component status (read-only)").pack(anchor="w", pady=(8, 0))
        status_shell = ttk.Frame(left)
        status_shell.pack(anchor="w", fill="both")
        status_vsb = ttk.Scrollbar(status_shell, orient="vertical")
        self._comp_status_tree = ttk.Treeview(
            status_shell,
            columns=("field", "value"),
            show="headings",
            height=11,
            yscrollcommand=status_vsb.set,
        )
        status_vsb.config(command=self._comp_status_tree.yview)
        self._comp_status_tree.heading("field", text="Field")
        self._comp_status_tree.column("field", width=150, stretch=False, anchor="w")
        self._comp_status_tree.heading("value", text="Value")
        self._comp_status_tree.column("value", width=170, stretch=True, anchor="w")
        self._comp_status_tree.pack(side="left", fill="both")
        status_vsb.pack(side="left", fill="y")

        right = ttk.Frame(tab)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=4)

        header_row = ttk.Frame(right)
        header_row.pack(fill="x", pady=(0, 4))
        ttk.Label(
            header_row, text="Components", font=("Segoe UI", 10, "bold")
        ).pack(side="left", padx=(2, 0))
        ttk.Button(
            header_row, text="Save", command=self._on_components_save
        ).pack(side="right")

        # Group 선택 + Add/Edit/Delete 한 줄로 통합.
        control_row = ttk.Frame(right)
        control_row.pack(fill="x", pady=(0, 6))
        ttk.Label(control_row, text="Add to group:").pack(side="left", padx=(2, 4))
        self._comp_group_combo = ttk.Combobox(
            control_row,
            values=[_group_display_label(label) for _, label, _ in COMPONENT_GROUPS],
            state="readonly",
            width=24,
        )
        self._comp_group_combo.current(0)
        self._comp_group_combo.pack(side="left")
        self._comp_group_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._on_components_group_changed()
        )
        ttk.Button(
            control_row, text="Delete", command=self._on_components_delete_row
        ).pack(side="right", padx=(2, 0))
        ttk.Button(
            control_row, text="Edit", command=self._on_components_edit_row
        ).pack(side="right", padx=(2, 0))
        ttk.Button(
            control_row, text="Add", command=self._on_components_add_row
        ).pack(side="right", padx=(2, 0))

        body = ttk.Frame(right)
        body.pack(fill="both", expand=True)

        _PREV_COLS = ("group", "Item_Code", "option_code", "size_from", "size_to", "component_name")
        tree_vsb = ttk.Scrollbar(body, orient="vertical")
        tv = ttk.Treeview(
            body, columns=_PREV_COLS, show="headings", height=16,
            yscrollcommand=tree_vsb.set,
        )
        tree_vsb.config(command=tv.yview)
        tv.heading("group",           text="Group");        tv.column("group",           width=110, stretch=False, anchor="w")
        tv.heading("Item_Code",       text="Item Code");    tv.column("Item_Code",       width=110, stretch=False, anchor="w")
        tv.heading("option_code",     text="Option Code");  tv.column("option_code",     width=100, stretch=False, anchor="w")
        tv.heading("size_from",       text="Size From");    tv.column("size_from",       width=75,  stretch=False, anchor="center")
        tv.heading("size_to",         text="Size To");      tv.column("size_to",         width=75,  stretch=False, anchor="center")
        tv.heading("component_name",  text="Component");    tv.column("component_name",  width=280, stretch=True,  anchor="w")
        tv.pack(side="left", fill="both", expand=True)
        tree_vsb.pack(side="left", fill="y")
        tv.bind("<Double-1>", lambda _e: self._on_components_edit_row())
        tv.bind("<<TreeviewSelect>>", lambda _e: self._on_components_row_selected())
        self._comp_tree = tv

        self._comp_working_rows: dict[str, list[dict[str, str]]] = {sn: [] for sn, _, _ in COMPONENT_GROUPS}
        self._comp_working_class: str | None = None
        self._comp_select_guard: bool = False

        self._refresh_components_class_list()

    def _on_components_group_changed(self) -> None:
        """Group 콤보는 Add 대상 그룹만 지정 — 통합 목록은 갱신/전환하지 않는다."""
        label = self._comp_group_combo.get()
        self._comp_current_group = self._comp_group_label_to_sheet.get(
            label, COMPONENT_GROUPS[0][0]
        )

    def _selected_component_location(self) -> tuple[str, int] | None:
        """통합 목록에서 선택된 행의 (sheet_name, group 내 index) 반환."""
        if not hasattr(self, "_comp_tree"):
            return None
        sel = self._comp_tree.selection()
        if not sel:
            return None
        return self._comp_item_map.get(sel[0])

    def _on_components_row_selected(self) -> None:
        """선택된 행의 필드/값을 read-only status 트리에 표시 (Edit 폼과 동일 항목)."""
        if not hasattr(self, "_comp_status_tree"):
            return
        for item in self._comp_status_tree.get_children():
            self._comp_status_tree.delete(item)
        loc = self._selected_component_location()
        if loc is None:
            return
        sheet_name, idx = loc
        rows = self._comp_working_rows.get(sheet_name, [])
        if not (0 <= idx < len(rows)):
            return
        row = rows[idx]
        _, _, headers = next(g for g in COMPONENT_GROUPS if g[0] == sheet_name)
        for h in headers:
            if h == "Class_Name":
                continue
            stored = (row.get(h, "") or "").strip()
            self._comp_status_tree.insert(
                "", "end", values=(h, _component_value_display(sheet_name, h, stored))
            )

    def _refresh_components_class_list(self) -> None:
        if not hasattr(self, "_comp_class_list"):
            return
        prev = self._comp_class_list.curselection()
        self._comp_select_guard = True
        try:
            self._comp_class_list.delete(0, "end")
            for row in self._bundle.class_define_rows:
                cn = (row.get("Class_Name") or "").strip() or "undefined"
                self._comp_class_list.insert("end", cn)
            _listbox_apply_stripes(self._comp_class_list)
            if prev and prev[0] < self._comp_class_list.size():
                self._comp_class_list.selection_set(prev[0])
            elif self._comp_class_list.size() > 0:
                self._comp_class_list.selection_set(0)
                self._comp_class_list.see(0)
                _listbox_apply_stripes(self._comp_class_list)
        finally:
            self._comp_select_guard = False

        sel = self._comp_class_list.curselection()
        new_cn: str | None = None
        if sel:
            idx = int(sel[0])
            if 0 <= idx < len(self._bundle.class_define_rows):
                new_cn = (self._bundle.class_define_rows[idx].get("Class_Name") or "").strip() or None
        self._comp_working_class = new_cn
        self._load_components_buffer_for(new_cn)
        self._refresh_components_preview()

    def _on_components_class_selected(self) -> None:
        if getattr(self, "_comp_select_guard", False):
            return
        sel = self._comp_class_list.curselection() if hasattr(self, "_comp_class_list") else ()
        new_cn: str | None = None
        if sel:
            idx = int(sel[0])
            if 0 <= idx < len(self._bundle.class_define_rows):
                new_cn = (self._bundle.class_define_rows[idx].get("Class_Name") or "").strip() or None
        if new_cn == self._comp_working_class:
            return
        if self._comp_working_class is not None and self._components_buffer_dirty():
            ok = messagebox.askyesno(
                "Unsaved changes",
                f"Class '{self._comp_working_class}'에 저장되지 않은 변경 사항이 있습니다.\n폐기하고 다른 클래스로 이동할까요?",
                parent=self,
            )
            if not ok:
                self._restore_components_class_selection()
                return
        self._comp_working_class = new_cn
        self._load_components_buffer_for(new_cn)
        self._refresh_components_preview()

    def _restore_components_class_selection(self) -> None:
        target = self._comp_working_class
        if not target or not hasattr(self, "_comp_class_list"):
            return
        self._comp_select_guard = True
        try:
            self._comp_class_list.selection_clear(0, "end")
            for i, row in enumerate(self._bundle.class_define_rows):
                cn = (row.get("Class_Name") or "").strip()
                if cn == target:
                    self._comp_class_list.selection_set(i)
                    self._comp_class_list.see(i)
                    _listbox_apply_stripes(self._comp_class_list)
                    break
        finally:
            self._comp_select_guard = False

    def _load_components_buffer_for(self, class_name: str | None) -> None:
        self._comp_working_rows = {sn: [] for sn, _, _ in COMPONENT_GROUPS}
        if not class_name:
            return
        for sheet_name, _, _headers in COMPONENT_GROUPS:
            for r in self._bundle.component_rows.get(sheet_name, []):
                if (r.get("Class_Name") or "").strip() != class_name:
                    continue
                self._comp_working_rows[sheet_name].append(
                    {k: v for k, v in r.items() if k != "Class_Name"}
                )

    def _components_buffer_dirty(self) -> bool:
        cn = self._comp_working_class
        if cn is None:
            return False
        for sheet_name, _, headers in COMPONENT_GROUPS:
            keys = [h for h in headers if h != "Class_Name"]
            bundle_rows = [
                tuple((r.get(k, "") or "").strip() for k in keys)
                for r in self._bundle.component_rows.get(sheet_name, [])
                if (r.get("Class_Name") or "").strip() == cn
            ]
            buffer_rows = [
                tuple((r.get(k, "") or "").strip() for k in keys)
                for r in self._comp_working_rows.get(sheet_name, [])
            ]
            if bundle_rows != buffer_rows:
                return True
        return False

    def _refresh_components_preview(self) -> None:
        """선택 Class 의 전 그룹 component 행을 하나의 통합 목록에 표시."""
        if not hasattr(self, "_comp_tree"):
            return
        tv = self._comp_tree
        for item in tv.get_children():
            tv.delete(item)
        self._comp_item_map = {}
        # status 패널도 선택 해제 상태로 초기화.
        if hasattr(self, "_comp_status_tree"):
            for item in self._comp_status_tree.get_children():
                self._comp_status_tree.delete(item)
        cn = self._comp_working_class
        if not cn:
            return
        for sheet_name, label, _headers in COMPONENT_GROUPS:
            rows = self._comp_working_rows.get(sheet_name, [])
            sf_col = _SHEET_SIZE_FROM.get(sheet_name, "Size_From")
            st_col = _SHEET_SIZE_TO.get(sheet_name, "Size_To")
            group_label = _group_display_label(label)
            for idx, row in enumerate(rows):
                iid = tv.insert("", "end", values=(
                    group_label,
                    row.get("Item_Code", ""),
                    row.get("Option_Code", ""),
                    row.get(sf_col, ""),
                    row.get(st_col, ""),
                    _combined_component_name(sheet_name, row),
                ))
                self._comp_item_map[iid] = (sheet_name, idx)

    def _ensure_components_class_ready(self, cn: str) -> bool:
        """Add/Edit를 허용하기 전 Class_Define 필수 필드/Schedule/값 검증을 모두 통과해야 True."""
        self._save_class_detail_to_row()
        missing = self._bundle.class_define_missing_fields(cn)
        if missing:
            messagebox.showwarning(
                "Class not ready",
                f"Class '{cn}' must have these fields set before editing components:\n\n"
                + "\n".join(f"  • {f}" for f in missing),
                parent=self,
            )
            return False
        errors = self._bundle.class_define_value_errors(cn)
        if errors:
            messagebox.showerror(
                "Invalid values",
                f"Class '{cn}' 값 검증 실패:\n\n"
                + "\n".join(f"  • {e}" for e in errors),
                parent=self,
            )
            return False
        return True

    def _on_components_save(self) -> None:
        cn = self._comp_working_class
        if not cn:
            messagebox.showinfo("Components", "Select a Class on the left first.", parent=self)
            return
        for sheet_name, _, _headers in COMPONENT_GROUPS:
            all_rows = self._bundle.component_rows.get(sheet_name, [])
            other_rows = [r for r in all_rows if (r.get("Class_Name") or "").strip() != cn]
            new_rows = [
                {**r, "Class_Name": cn} for r in self._comp_working_rows.get(sheet_name, [])
            ]
            self._bundle.component_rows[sheet_name] = other_rows + new_rows
        self._refresh_components_preview()

    def _on_components_add_row(self) -> None:
        sheet_name = self._comp_current_group
        cn = self._comp_working_class
        if not cn:
            messagebox.showinfo("Components", "Select a Class on the left first.", parent=self)
            return
        if not self._ensure_components_class_ready(cn):
            return
        _, _, headers = next(g for g in COMPONENT_GROUPS if g[0] == sheet_name)
        display_hdrs = [h for h in headers if h != "Class_Name"]
        active_sizes = self._active_sizes_for_class(cn)
        dlg = _ComponentRowEditDialog(
            self,
            title=f"Add — {sheet_name}",
            sheet_name=sheet_name,
            headers=display_hdrs,
            active_sizes=active_sizes,
        )
        self.wait_window(dlg)
        if dlg.result is not None:
            self._comp_working_rows.setdefault(sheet_name, []).append(dlg.result)
            self._refresh_components_preview()

    def _on_components_edit_row(self) -> None:
        cn = self._comp_working_class
        if not cn:
            messagebox.showinfo("Components", "Select a Class on the left first.", parent=self)
            return
        loc = self._selected_component_location()
        if loc is None:
            messagebox.showinfo("Components", "Select a row first.", parent=self)
            return
        sheet_name, idx = loc
        rows = self._comp_working_rows.get(sheet_name, [])
        if idx < 0 or idx >= len(rows):
            return
        if not self._ensure_components_class_ready(cn):
            return
        _, _, headers = next(g for g in COMPONENT_GROUPS if g[0] == sheet_name)
        display_hdrs = [h for h in headers if h != "Class_Name"]
        active_sizes = self._active_sizes_for_class(cn)
        dlg = _ComponentRowEditDialog(
            self,
            title=f"Edit — {sheet_name}",
            sheet_name=sheet_name,
            headers=display_hdrs,
            active_sizes=active_sizes,
            initial=rows[idx],
        )
        self.wait_window(dlg)
        if dlg.result is not None:
            rows[idx] = dlg.result
            self._refresh_components_preview()

    def _on_components_delete_row(self) -> None:
        if not self._comp_working_class:
            messagebox.showinfo("Components", "Select a Class on the left first.", parent=self)
            return
        loc = self._selected_component_location()
        if loc is None:
            messagebox.showinfo("Components", "Select a row first.", parent=self)
            return
        sheet_name, idx = loc
        rows = self._comp_working_rows.get(sheet_name, [])
        if not (0 <= idx < len(rows)):
            return
        item_code = (rows[idx].get("Item_Code") or "").strip()
        label = item_code if item_code else "(unnamed)"
        if not messagebox.askyesno(
            "Delete row",
            f"Delete this row from {sheet_name}?\n\n  • {label}",
            parent=self,
        ):
            return
        del rows[idx]
        self._refresh_components_preview()

    def _flush_and_validate(self) -> bool:
        """현재 폼 입력을 bundle에 반영하고 모델 검증을 통과하면 True."""
        idx = self._current_class_idx()
        if idx is not None:
            self._save_class_row_at_index(idx)
        value_errors: list[str] = []
        for row in self._bundle.class_define_rows:
            cn = (row.get("Class_Name") or "").strip()
            if not cn:
                continue
            for e in self._bundle.class_define_value_errors(cn):
                value_errors.append(f"[{cn}] {e}")
        if value_errors:
            messagebox.showerror("Validation", "\n".join(value_errors), parent=self)
            return False
        self._bundle.global_settings = copy.deepcopy(self._global_settings)
        errs = self._bundle.validate()
        if errs:
            messagebox.showerror("Validation", "\n".join(errs), parent=self)
            return False
        warns = self._bundle.validation_warnings()
        if warns:
            messagebox.showwarning("Validation Warning", "\n".join(warns), parent=self)
        return True

    def _persist_to_disk(self) -> bool:
        """현재 bundle 을 디스크에 기록. 성공 True / 검증 실패·경로 취소·IO 실패 False.
        Component 버퍼 커밋은 호출 전에 끝나 있어야 한다 (여기선 bundle 만 다룸)."""
        if not self._flush_and_validate():
            return False
        path = self._project_path
        if not path:
            chosen = file_handler.select_project_save_path(self)
            if not chosen:
                return False
            path = chosen
        try:
            save_project(self._bundle, path)
        except (OSError, ProjectFileError) as exc:
            messagebox.showerror("Save Project", f"저장 실패:\n{exc}", parent=self)
            return False
        self._project_path = path
        self._on_disk_snapshot = copy.deepcopy(self._bundle)
        self.title(f"RefPMS — {Path(path).name}")
        return True

    def _on_save_project(self) -> None:
        # 미커밋 Component 버퍼가 있으면 저장에 포함할지 먼저 확인 (조용한 유실 방지).
        if self._components_buffer_dirty():
            if not messagebox.askyesno(
                "Save Project",
                "저장되지 않은 Component 변경이 있습니다.\n포함해서 저장하시겠습니까?",
                parent=self,
            ):
                return
            self._on_components_save()
        if self._persist_to_disk():
            messagebox.showinfo("Save Project", f"Saved:\n{self._project_path}", parent=self)

    def _on_export_xlsx(self) -> None:
        if not self._flush_and_validate():
            return
        save_dir = file_handler.select_save_folder(self)
        if not save_dir:
            return
        try:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = Path(save_dir) / "template" / stamp
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / DEFAULT_TEMPLATE_FILENAME
            generate_class_define_template(output_path=out_path, class_level=self._bundle)
        except Exception as exc:
            messagebox.showerror("Export xlsx", f"내보내기 실패:\n{exc}", parent=self)
            return
        messagebox.showinfo("Export xlsx", f"Exported:\n{out_path}", parent=self)

    def _on_close(self) -> None:
        idx = self._current_class_idx()
        if idx is not None:
            self._save_class_row_at_index(idx)
        self._bundle.global_settings = copy.deepcopy(self._global_settings)
        # 미커밋 Component 버퍼가 있으면 먼저 처리 — bundle 레벨 비교에는 안 잡히므로
        # 여기서 막지 않으면 조용히 유실된다. '아니오'는 아래 bundle 레벨 확인으로 진행.
        if self._components_buffer_dirty():
            if messagebox.askyesno(
                "Close Project",
                "저장 안 된 Component 변경이 있습니다.\n저장하고 닫으시겠습니까?",
                parent=self,
            ):
                self._on_components_save()
                if not self._persist_to_disk():
                    return  # 저장 실패/취소 → 닫지 않음
                self.destroy()
                return
            # 아니오 → 버퍼 폐기, 아래 bundle 레벨 검사로 진행
        if self._bundle != self._on_disk_snapshot:
            if not messagebox.askyesno(
                "Close Project",
                "저장하지 않은 변경이 있습니다. 그래도 닫으시겠습니까?",
                parent=self,
            ):
                return
        self.destroy()


def run_class_level_wizard(
    parent: tk.Tk,
    initial_bundle: ClassLevelBundle | None = None,
    initial_project_path: str | None = None,
) -> None:
    """프로젝트 wizard 실행. Save / Export / Close 모두 wizard 내부에서 처리."""
    seed = copy.deepcopy(initial_bundle) if initial_bundle is not None else None
    dlg = ClassLevelWizard(
        parent, initial_bundle=seed, initial_project_path=initial_project_path
    )
    parent.wait_window(dlg)
