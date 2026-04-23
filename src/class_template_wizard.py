"""Class-level template wizard (English UI) — runs before template xlsx is built."""

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable, Literal

import config
from class_level_model import (
    ClassLevelBundle,
    ClassTemplateGlobalSettings,
    NamedSizeTable,
    SizeSelection,
    default_size_selection_from_catalog,
    normalizeScheduleValue,
    row_dict_for_headers,
    scheduleAllowlist,
)
from class_spec import class_base_material_group_keys, flange_pt_class_rating_options
from size_matrix_common import normalize_nominal_mode
from size_matrix_editor import run_size_matrix_editor
from template_generator import SCHEDULE_HEADERS
from units_notation_headers import bracket_unit_header, class_define_headers

_CLASS_DETAIL_LABEL_WIDTH = 28
_CLASS_DETAIL_VALUE_PADX = (8, 0)

# Light-theme list / sheet visuals (zebra ≈ thin row separation)
_STRIPE_A = "#ffffff"
_STRIPE_B = "#f0f1f4"
_LIST_HOVER = "#dceaf7"

_LAST_CLASS_LEVEL_BUNDLE: ClassLevelBundle | None = None
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

    ttk.Label(win, text="Select the Nominal Size System for this table.\nThis cannot be changed after creation.", wraplength=300).pack(padx=20, pady=(16, 8))

    var = tk.StringVar(value="NPS")
    rb_frame = ttk.Frame(win)
    rb_frame.pack(padx=20, pady=8)
    ttk.Radiobutton(rb_frame, text="NPS (ASME B36.10)", variable=var, value="NPS").pack(anchor="w", pady=4)
    ttk.Radiobutton(rb_frame, text="DN (ISO 6708)", variable=var, value="DN").pack(anchor="w", pady=4)

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
        name = simpledialog.askstring("Add table", "Table_Code (unique name):", parent=parent)
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


class ClassLevelWizard(tk.Toplevel):
    def __init__(self, parent: tk.Tk, initial_bundle: ClassLevelBundle | None = None) -> None:
        super().__init__(parent)
        self.title("Class-level template data")
        self.geometry("920x620")
        self.transient(parent)
        self.grab_set()
        self.result: ClassLevelBundle | None = None
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
            self._global_settings = ClassTemplateGlobalSettings(
                size_selection=default_size_selection_from_catalog()
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

        self._schedule_refresh_class_list: Callable[[], None] = lambda: None
        self._schedule_sync_size_range: Callable[[str], None] = lambda _cn: None
        self._reducing_tab_refresh: Callable[[], None] = lambda: None
        self._branch_tab_refresh: Callable[[], None] = lambda: None
        self._tab_global_setting(nb)
        self._tab_class(nb)
        self._tab_schedule(nb)
        self._tab_reducing_tables(nb)
        self._tab_branch_tables(nb)

        bf = ttk.Frame(self)
        bf.pack(fill="x", padx=8, pady=8)
        ttk.Button(bf, text="OK — build template", command=self._on_ok).pack(side="right", padx=6)
        ttk.Button(bf, text="Cancel", command=self._on_cancel).pack(side="right", padx=6)

    def _refresh_derived_from_global_settings(self) -> None:
        """Global settings 변경 시 헤더·corrosion 레퍼런스·temp/press 키 재계산."""
        gs = self._global_settings
        self._class_design_temp_u = gs.design_temperature_unit
        self._class_design_press_u = gs.design_pressure_unit
        self._class_define_headers = class_define_headers(
            gs.design_temperature_unit, gs.design_pressure_unit
        )
        (
            self._class_temp_from_h,
            self._class_temp_to_h,
            self._class_press_from_h,
            self._class_press_to_h,
        ) = ClassLevelWizard._resolve_temperature_pressure_header_keys(self._class_define_headers)
        self._corrosion_unit_symbol = _corrosion_allowance_unit_symbol(gs.unit_system)
        self._corrosion_combo_values = _corrosion_reference_values_for(gs.unit_system)

    def _new_class_row(self) -> dict[str, str]:
        row = row_dict_for_headers(self._class_define_headers)
        row[_CORROSION_ALLOWANCE_KEY] = self._corrosion_default_value
        return row

    def _rekey_class_rows_to_current_headers(
        self, old_temp_from: str, old_temp_to: str, old_press_from: str, old_press_to: str
    ) -> None:
        """단위 변경으로 헤더 키가 바뀐 경우 각 row 의 키를 새 헤더로 재매핑."""
        rename_map: dict[str, str] = {}
        if old_temp_from and old_temp_from != self._class_temp_from_h:
            rename_map[old_temp_from] = self._class_temp_from_h
        if old_temp_to and old_temp_to != self._class_temp_to_h:
            rename_map[old_temp_to] = self._class_temp_to_h
        if old_press_from and old_press_from != self._class_press_from_h:
            rename_map[old_press_from] = self._class_press_from_h
        if old_press_to and old_press_to != self._class_press_to_h:
            rename_map[old_press_to] = self._class_press_to_h
        if not rename_map:
            return
        for row in self._bundle.class_define_rows:
            for old_key, new_key in rename_map.items():
                if old_key in row:
                    row[new_key] = row.pop(old_key)

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

    @staticmethod
    def _resolve_temperature_pressure_header_keys(
        headers: list[str],
    ) -> tuple[str, str, str, str]:
        tf = tt = pf = pt = ""
        for x in headers:
            if x.startswith("Design_Temperature_From"):
                tf = x
            elif x.startswith("Design_Temperature_To"):
                tt = x
            elif x.startswith("Design_Pressure_From"):
                pf = x
            elif x.startswith("Design_Pressure_To"):
                pt = x
        return tf, tt, pf, pt

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

    def _tab_global_setting(self, nb: ttk.Notebook) -> None:
        """Template 전역 단위 체계 + Size Selection 편집 탭 — 모든 Class 에 공통 적용."""
        tab = ttk.Frame(nb)
        nb.add(tab, text="Global Setting")

        box = ttk.LabelFrame(tab, text="Template-global unit system")
        box.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Label(
            box,
            text=(
                "These units apply to ALL classes in this template. "
                "Temperature and pressure columns on Class_Define use the unit selected here."
            ),
            wraplength=560,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(6, 8))

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
        self._design_press_combo.grid(row=3, column=1, sticky="ew", padx=(8, 8), pady=4)

        box.columnconfigure(1, weight=1)

        self._refresh_design_unit_options(preserve_selection=True)

        self._design_press_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._on_design_units_changed()
        )

        self._build_size_selection_panel(tab)

    def _build_size_selection_panel(self, parent: tk.Widget) -> None:
        """Global Size Selection panel — NPS / DN / Use 표 + Save 버튼.

        - 한 행 = NPS↔DN 1:1 페어. 짝 없는 쪽은 '-'.
        - 체크는 메모리에만 적용되고, Save 를 눌러야 self._global_settings.size_selection 에 반영.
        - Save 시점에 사용 중인 사이즈를 해제하면 위반 목록을 띄우고 차단.
        """
        box = ttk.LabelFrame(parent, text="Size Selection (Global) — sizes available to all classes")
        box.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        ttk.Label(
            box,
            text=(
                "Check the sizes you want to make available in this template. "
                "Class_Define / Reducing / Branch tables can only pick Size_From / Size_To from checked sizes. "
                "Press Save to apply."
            ),
            wraplength=720,
        ).pack(anchor="w", padx=8, pady=(6, 4))

        toolbar = ttk.Frame(box)
        toolbar.pack(fill="x", padx=8, pady=(0, 4))
        save_btn = ttk.Button(
            toolbar, text="Save", command=lambda: self._save_size_selection()
        )
        save_btn.pack(side="right")
        ttk.Button(
            toolbar,
            text="Defaults (preferred only)",
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
        canvas = tk.Canvas(scroll_host, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(scroll_host, orient="vertical", command=canvas.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=vsb.set)
        grid_frame = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=grid_frame, anchor="nw")

        def _on_grid_config(_e=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
            try:
                canvas.itemconfigure(canvas_window, width=canvas.winfo_width())
            except tk.TclError:
                pass

        grid_frame.bind("<Configure>", _on_grid_config)
        canvas.bind("<Configure>", _on_grid_config)

        def _mw(_e):
            canvas.yview_scroll(int(-1 * (_e.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _mw)
        grid_frame.bind("<MouseWheel>", _mw)

        # Header row
        ttk.Label(grid_frame, text="NPS", width=10, anchor="center", font=("", 9, "bold")).grid(
            row=0, column=0, padx=8, pady=(4, 6), sticky="w"
        )
        ttk.Label(grid_frame, text="DN", width=10, anchor="center", font=("", 9, "bold")).grid(
            row=0, column=1, padx=8, pady=(4, 6), sticky="w"
        )
        ttk.Label(grid_frame, text="Use", width=6, anchor="center", font=("", 9, "bold")).grid(
            row=0, column=2, padx=8, pady=(4, 6), sticky="w"
        )

        pairs = config.load_nps_dn_pairs()
        nps_active = set(self._global_settings.size_selection.nps)
        dn_active = set(self._global_settings.size_selection.dn)

        self._size_sel_pairs: list[dict[str, str]] = pairs
        self._size_sel_vars: list[tk.BooleanVar] = []
        for pair in pairs:
            nps = (pair.get("nps") or "-").strip() or "-"
            dn = (pair.get("dn") or "-").strip() or "-"
            checked = (nps != "-" and nps in nps_active) or (dn != "-" and dn in dn_active)
            self._size_sel_vars.append(tk.BooleanVar(value=checked))

        # Use 2-column layout to keep panel compact (col group 0..2 and col group 3..5).
        rows_per_col_group = (len(pairs) + 1) // 2
        for idx, pair in enumerate(pairs):
            col_group = 0 if idx < rows_per_col_group else 1
            within = idx if col_group == 0 else idx - rows_per_col_group
            base_col = col_group * 4  # 0 or 4
            r = within + 1
            nps = (pair.get("nps") or "-").strip() or "-"
            dn = (pair.get("dn") or "-").strip() or "-"
            ttk.Label(grid_frame, text=nps, width=10, anchor="e").grid(
                row=r, column=base_col + 0, padx=(8, 4), pady=1, sticky="e"
            )
            ttk.Label(grid_frame, text=dn, width=10, anchor="e").grid(
                row=r, column=base_col + 1, padx=(4, 4), pady=1, sticky="e"
            )
            ttk.Checkbutton(grid_frame, variable=self._size_sel_vars[idx]).grid(
                row=r, column=base_col + 2, padx=(4, 16), pady=1, sticky="w"
            )

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
        # Schedule tab 의 Size 드롭다운도 새로 고침
        self._schedule_refresh_class_list()

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

        old_temp_from = self._class_temp_from_h
        old_temp_to = self._class_temp_to_h
        old_press_from = self._class_press_from_h
        old_press_to = self._class_press_to_h

        self._save_class_detail_to_row()
        self._global_settings = ClassTemplateGlobalSettings(
            unit_system=new_system,
            design_temperature_unit=new_temp,
            design_pressure_unit=new_press,
        )
        self._refresh_derived_from_global_settings()
        self._rekey_class_rows_to_current_headers(
            old_temp_from, old_temp_to, old_press_from, old_press_to
        )
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
        lf.pack(side="left", fill="y", padx=4, pady=4)
        ttk.Label(lf, text="Class rows").pack(anchor="w")
        self._class_list_shell = tk.Frame(
            lf,
            highlightthickness=1,
            highlightbackground="#b0b0b0",
            highlightcolor="#b0b0b0",
            bg="#fafafa",
        )
        self._class_list_holder = tk.Frame(self._class_list_shell, bg="#fafafa")
        self._class_list = tk.Listbox(
            self._class_list_holder,
            width=28,
            height=22,
            exportselection=False,
            relief="flat",
            bd=0,
            highlightthickness=0,
            bg=_STRIPE_A,
            selectbackground="#2b6cb0",
            selectforeground="white",
            activestyle="none",
        )
        self._class_list.pack(fill="both", expand=True, padx=1, pady=1)
        self._class_list_ph = _canvas_dashed_empty_state(
            self._class_list_shell,
            'No class rows yet. Use "Add row".',
            height=160,
            bg="#fafafa",
        )
        self._class_list_shell.pack(fill="both", expand=True)
        self._class_list.bind("<<ListboxSelect>>", lambda _e: self._load_class_detail())
        _bind_listbox_stripes_and_hover(self._class_list)
        bf = ttk.Frame(lf)
        bf.pack(fill="x", pady=4)
        ttk.Button(bf, text="Add row", command=self._add_class_row).pack(fill="x", pady=2)
        ttk.Button(bf, text="Delete row", command=self._del_class_row).pack(fill="x", pady=2)

        self._class_rf = ttk.LabelFrame(tab, text="Selected row")
        self._class_rf.pack(side="left", fill="both", expand=True, padx=8, pady=4)
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
        rows_f = ttk.Frame(self._class_rf)
        rows_f.pack(fill="both", expand=True)
        self._class_rows_frame = rows_f

        pair_skip: set[str] = set()
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
                ttk.Label(
                    rows_f,
                    text=bracket_unit_header("Design Temperature", self._class_design_temp_u),
                    width=lw,
                ).grid(row=grid_row, column=0, sticky="w", pady=1)
                sub = ttk.Frame(rows_f)
                sub.grid(row=grid_row, column=1, sticky="ew", pady=1, padx=px)
                v_tf = tk.StringVar()
                v_tt = tk.StringVar()
                self._class_entries[self._class_temp_from_h] = v_tf
                self._class_entries[self._class_temp_to_h] = v_tt
                e_tf = ttk.Entry(sub, textvariable=v_tf, width=18)
                ttk.Label(sub, text="~").grid(row=0, column=1, padx=6)
                e_tt = ttk.Entry(sub, textvariable=v_tt, width=18)
                e_tf.grid(row=0, column=0, sticky="ew")
                e_tt.grid(row=0, column=2, sticky="ew")
                sub.columnconfigure(0, weight=1)
                sub.columnconfigure(2, weight=1)
                grid_row += 1
                continue

            if self._use_combined_temperature_pressure_rows() and h == self._class_press_from_h:
                ttk.Label(
                    rows_f,
                    text=bracket_unit_header("Design Pressure", self._class_design_press_u),
                    width=lw,
                ).grid(row=grid_row, column=0, sticky="w", pady=1)
                subp = ttk.Frame(rows_f)
                subp.grid(row=grid_row, column=1, sticky="ew", pady=1, padx=px)
                v_pf = tk.StringVar()
                v_pt = tk.StringVar()
                self._class_entries[self._class_press_from_h] = v_pf
                self._class_entries[self._class_press_to_h] = v_pt
                e_pf = ttk.Entry(subp, textvariable=v_pf, width=18)
                ttk.Label(subp, text="~").grid(row=0, column=1, padx=6)
                e_pt = ttk.Entry(subp, textvariable=v_pt, width=18)
                e_pf.grid(row=0, column=0, sticky="ew")
                e_pt.grid(row=0, column=2, sticky="ew")
                subp.columnconfigure(0, weight=1)
                subp.columnconfigure(2, weight=1)
                grid_row += 1
                continue

            if h == _CORROSION_ALLOWANCE_KEY:
                ca_label = bracket_unit_header("Corrosion_Allowance", self._corrosion_unit_symbol)
                ttk.Label(rows_f, text=ca_label, width=lw).grid(row=grid_row, column=0, sticky="w", pady=1)
                cb = ttk.Combobox(
                    rows_f,
                    width=42,
                    state="normal",
                    values=self._corrosion_combo_values,
                )
                cb.grid(row=grid_row, column=1, sticky="ew", pady=1, padx=px)
                self._class_combos[h] = cb
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
                cb.grid(row=grid_row, column=1, sticky="ew", pady=1, padx=px)
                self._class_combos[h] = cb
            elif h == "Nominal_Size_System":
                cb = ttk.Combobox(
                    rows_f,
                    width=42,
                    state="readonly",
                    values=list(self._nominal_size_options),
                )
                cb.grid(row=grid_row, column=1, sticky="ew", pady=1, padx=px)
                cb.bind(
                    "<<ComboboxSelected>>",
                    lambda _e: self._on_nominal_size_system_changed(),
                )
                self._class_combos[h] = cb
            elif h in ("Size_From", "Size_To"):
                cb = ttk.Combobox(
                    rows_f,
                    width=42,
                    state="readonly",
                    values=[""],
                )
                cb.grid(row=grid_row, column=1, sticky="ew", pady=1, padx=px)
                self._class_combos[h] = cb
            elif h == "Class_Base_Material":
                cb = ttk.Combobox(
                    rows_f,
                    width=42,
                    state="readonly",
                    values=self._material_combo_values,
                )
                cb.grid(row=grid_row, column=1, sticky="ew", pady=1, padx=px)
                self._class_combos[h] = cb
            elif h == "Class_Rating":
                cb = ttk.Combobox(
                    rows_f,
                    width=42,
                    state="readonly",
                    values=self._rating_combo_values,
                )
                cb.grid(row=grid_row, column=1, sticky="ew", pady=1, padx=px)
                self._class_combos[h] = cb
            elif h in ("Branch_Table_1", "Branch_Table_2"):
                cb = ttk.Combobox(rows_f, width=42, state="readonly", values=list(self._branch_names()))
                cb.grid(row=grid_row, column=1, sticky="ew", pady=1, padx=px)
                self._class_combos[h] = cb
            elif h in ("Reducing_Table_1", "Reducing_Table_2"):
                cb = ttk.Combobox(rows_f, width=42, state="readonly", values=list(self._reducing_names()))
                cb.grid(row=grid_row, column=1, sticky="ew", pady=1, padx=px)
                self._class_combos[h] = cb
            else:
                v = tk.StringVar()
                e = ttk.Entry(rows_f, textvariable=v, width=44)
                e.grid(row=grid_row, column=1, sticky="ew", pady=1, padx=px)
                self._class_entries[h] = v
                if h == "Class_Name":
                    e.bind("<FocusOut>", self._on_class_name_focus_out, add="+")
                elif h == "Revision_No":
                    e.bind("<FocusOut>", self._on_revision_no_focus_out, add="+")
            grid_row += 1
        rows_f.columnconfigure(1, weight=1)

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
        self._save_class_detail_to_row()

    def _refresh_combo_lists(self) -> None:
        rvals = list(self._reducing_names())
        bvals = list(self._branch_names())
        idx = self._current_class_idx()
        mode = "NPS"
        if idx is not None and 0 <= idx < len(self._bundle.class_define_rows):
            mode = normalize_nominal_mode(
                self._bundle.class_define_rows[idx].get("Nominal_Size_System")
            )
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
            self._class_list_holder.pack(fill="both", expand=True)
        else:
            self._class_list_holder.pack_forget()
            self._class_list_ph.pack(fill="both", expand=True)
        _listbox_apply_stripes(self._class_list)
        self._schedule_refresh_class_list()

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

    def _tab_schedule(self, nb: ttk.Notebook) -> None:
        tab = ttk.Frame(nb)
        nb.add(tab, text="Schedule")

        outer = ttk.Frame(tab)
        outer.pack(fill="both", expand=True, padx=8, pady=8)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(0, weight=1)

        left = ttk.Frame(outer)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 8))
        ttk.Label(left, text="Class list").pack(anchor="w")
        class_lb = tk.Listbox(left, width=30, height=20, exportselection=False)
        class_lb.pack(fill="y", expand=False)
        _bind_listbox_stripes_and_hover(class_lb)

        right = ttk.Frame(outer)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        cols = ("Size_From", "Size_To", "Schedule")
        schedule_values = scheduleAllowlist()
        schedule_value_set = set(schedule_values)
        # size dropdown values for the currently selected class (updated on class select / size range save)
        size_range_values: dict[str, list[str]] = {}  # class_name -> sorted active sizes
        tree_holder = ttk.Frame(right)
        tree_holder.grid(row=0, column=0, sticky="nsew")
        tree_holder.grid_rowconfigure(0, weight=1)
        tree_holder.grid_columnconfigure(0, weight=1)
        tree = ttk.Treeview(
            tree_holder,
            columns=cols,
            show="headings",
            height=16,
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

        selected_class: dict[str, str] = {"name": ""}
        class_items: list[tuple[str, str]] = []
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

        def build_class_items() -> list[tuple[str, str]]:
            out: list[tuple[str, str]] = []
            for i, row in enumerate(self._bundle.class_define_rows, start=1):
                nm = str(row.get("Class_Name", "") or "").strip()
                label = nm if nm else f"(blank class #{i})"
                out.append((label, nm))
            return out

        def ensure_selected_class() -> None:
            nonlocal class_items
            if not class_items:
                selected_class["name"] = ""
                return
            names = [raw for _, raw in class_items]
            if selected_class["name"] not in names:
                selected_class["name"] = names[0]
            idx = names.index(selected_class["name"])
            class_lb.selection_clear(0, "end")
            class_lb.selection_set(idx)
            class_lb.activate(idx)
            class_lb.see(idx)

        def _rebuild_size_range_values() -> None:
            size_range_values.clear()
            for row in self._bundle.class_define_rows:
                nm = (row.get("Class_Name") or "").strip()
                if not nm:
                    continue
                size_range_values[nm] = list(self._active_sizes_for_class(nm))

        def refill_class_list() -> None:
            nonlocal class_items
            class_items = build_class_items()
            _rebuild_size_range_values()
            class_lb.delete(0, "end")
            for label, _raw in class_items:
                class_lb.insert("end", label)
            if class_items:
                ensure_selected_class()
            _listbox_apply_stripes(class_lb)
            refill_rows()

        def rows_for_selected() -> list[tuple[int, dict[str, str]]]:
            nm = selected_class["name"]
            if not nm:
                return []
            out: list[tuple[int, dict[str, str]]] = []
            for idx, row in enumerate(self._bundle.schedule_rows):
                if str(row.get("Class_Name", "") or "").strip() == nm:
                    out.append((idx, row))
            return out

        def refill_rows(select_iid: str | None = None) -> None:
            for iid in tree.get_children():
                tree.delete(iid)
            pairs = rows_for_selected()
            nm = selected_class["name"]
            known_sizes = set(size_range_values.get(nm, []))
            for vis_idx, (src_idx, row) in enumerate(pairs):
                iid = f"r{src_idx}"
                sf = str(row.get("Size_From", "") or "")
                st = str(row.get("Size_To", "") or "")
                out_of_range = known_sizes and (
                    (sf.strip() and sf.strip() not in known_sizes)
                    or (st.strip() and st.strip() not in known_sizes)
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

        def on_class_select(_e: tk.Event | None = None) -> None:
            sel = class_lb.curselection()
            if not sel:
                return
            idx = int(sel[0])
            if 0 <= idx < len(class_items):
                _close_editor_now()
                selected_class["name"] = class_items[idx][1]
                refill_rows()

        class_lb.bind("<<ListboxSelect>>", on_class_select)

        def add_row_for_selected() -> bool:
            nm = selected_class["name"]
            if not nm:
                messagebox.showinfo("Selection", "Select a class first.", parent=self)
                return False
            self._bundle.schedule_rows.append(
                {"Class_Name": nm, "Size_From": "", "Size_To": "", "Schedule": ""}
            )
            new_iid = f"r{len(self._bundle.schedule_rows) - 1}"
            refill_rows(select_iid=new_iid)
            start_edit(new_iid, "#1", None)
            return True

        def delete_selected_row() -> bool:
            sel = tree.selection()
            if not sel:
                return False
            src_idx = int(str(sel[0])[1:])
            if 0 <= src_idx < len(self._bundle.schedule_rows):
                self._bundle.schedule_rows.pop(src_idx)
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
                nm = selected_class["name"]
                sz_vals = size_range_values.get(nm, [])
                ent = ttk.Combobox(tree, values=sz_vals, state="normal")
            else:
                vcmd = (self.register(_validate_numeric_key), "%P")
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
                if col_id in ("#1", "#2") and not _is_numeric_text(new_raw):
                    messagebox.showerror(
                        "Invalid value",
                        "Size_From / Size_To columns only allow numeric values.",
                        parent=self,
                    )
                    ent.focus_set()
                    return False
                if col_id == "#3":
                    normalized = normalizeScheduleValue(new_raw)
                    if normalized and normalized not in schedule_value_set:
                        messagebox.showerror(
                            "Invalid schedule",
                            "Schedule must be selected from the standard allowlist.",
                            parent=self,
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
                if 0 <= src_idx < len(self._bundle.schedule_rows):
                    row = self._bundle.schedule_rows[src_idx]
                    row["Class_Name"] = selected_class["name"]
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
                    nm = selected_class["name"]
                    return size_range_values.get(nm, [])

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

            self.after_idle(begin_edit_after_select)
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

        row_btns = ttk.Frame(right)
        row_btns.grid(row=1, column=0, sticky="e", pady=(8, 0))
        ttk.Button(row_btns, text="Add row", command=add_row_for_selected).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(row_btns, text="Delete row", command=delete_selected_row).pack(
            side="left"
        )

        def sync_size_range_for_class(class_name: str) -> None:
            """Size Range 저장 후 해당 클래스의 드롭다운 값 갱신 및 경고 재표시."""
            _rebuild_size_range_values()
            if selected_class["name"] == class_name:
                refill_rows()

        self._schedule_refresh_class_list = refill_class_list
        self._schedule_sync_size_range: Callable[[str], None] = sync_size_range_for_class
        refill_class_list()

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

        ttk.Label(
            tab,
            text=(
                "Reducing tables (sheet: Reducing_Table) — one entry per Table_Code. "
                "Classes reference these by name via Reducing_Table_1 / Reducing_Table_2."
            ),
            wraplength=640,
        ).pack(anchor="w", padx=12, pady=(10, 0))

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

        ttk.Label(
            tab,
            text=(
                "Branch tables (sheet: Branch_Table) — one entry per Table_Code. "
                "Classes reference these by name via Branch_Table_1 / Branch_Table_2."
            ),
            wraplength=640,
        ).pack(anchor="w", padx=12, pady=(10, 0))

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

    def _on_ok(self) -> None:
        idx = self._current_class_idx()
        if idx is not None:
            self._save_class_row_at_index(idx)
        self._bundle.global_settings = copy.deepcopy(self._global_settings)
        errs = self._bundle.validate()
        if errs:
            messagebox.showerror("Validation", "\n".join(errs), parent=self)
            return
        warns = self._bundle.validation_warnings()
        if warns:
            messagebox.showwarning("Validation Warning", "\n".join(warns), parent=self)
        self.result = copy.deepcopy(self._bundle)
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()


def run_class_level_wizard(
    parent: tk.Tk,
    initial_bundle: ClassLevelBundle | None = None,
) -> ClassLevelBundle | None:
    global _LAST_CLASS_LEVEL_BUNDLE
    if initial_bundle is not None:
        seed = copy.deepcopy(initial_bundle)
    else:
        seed = copy.deepcopy(_LAST_CLASS_LEVEL_BUNDLE) if _LAST_CLASS_LEVEL_BUNDLE is not None else None
    dlg = ClassLevelWizard(parent, initial_bundle=seed)
    parent.wait_window(dlg)
    if dlg.result is not None:
        _LAST_CLASS_LEVEL_BUNDLE = copy.deepcopy(dlg.result)
    return dlg.result
