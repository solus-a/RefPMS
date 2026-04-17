"""Class-level template wizard (English UI) — runs before template xlsx is built."""

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable, Literal

import config
from class_level_model import (
    ClassLevelBundle,
    ClassSizeRange,
    NamedSizeTable,
    normalizeScheduleValue,
    row_dict_for_headers,
    scheduleAllowlist,
)
from class_spec import class_base_material_group_keys, flange_pt_class_rating_options
from size_matrix_editor import run_size_matrix_editor
from template_generator import JOINT_HEADERS, SCHEDULE_HEADERS
from units_notation_headers import (
    bracket_unit_header,
    class_define_headers,
    fluid_service_headers,
    read_design_units_from_merged,
)

_CLASS_DETAIL_LABEL_WIDTH = 28
_CLASS_DETAIL_VALUE_PADX = (8, 0)

# Light-theme list / sheet visuals (zebra ≈ thin row separation)
_STRIPE_A = "#ffffff"
_STRIPE_B = "#f0f1f4"
_LIST_HOVER = "#dceaf7"

_LAST_CLASS_LEVEL_BUNDLE: ClassLevelBundle | None = None
_CORROSION_ALLOWANCE_KEY = "Corrosion_Allowance"


def _project_selected_unit_system(merged: dict) -> str:
    un = merged.get("units_notation")
    if not isinstance(un, dict):
        return "Metric"
    us = un.get("unit_system")
    if not isinstance(us, dict):
        return "Metric"
    sel = str(us.get("selected", "Metric") or "Metric").strip()
    return "Imperial" if sel == "Imperial" else "Metric"


def _corrosion_allowance_unit_symbol(unit_system: str) -> str:
    return "inch" if unit_system == "Imperial" else "mm"


def _corrosion_reference_values(merged: dict) -> list[str]:
    vp = merged.get("validation_policy")
    if not isinstance(vp, dict):
        return []
    ca = vp.get("corrosion_allowance")
    if not isinstance(ca, dict):
        return []
    ref = ca.get("reference_values")
    if not isinstance(ref, dict):
        return []

    metric_raw = ref.get("metric_mm") if isinstance(ref.get("metric_mm"), list) else []
    imperial_raw = ref.get("imperial_inch") if isinstance(ref.get("imperial_inch"), list) else []

    ordered: list[str] = []
    seen: set[str] = set()
    for source in (metric_raw, imperial_raw):
        for v in source:
            sv = str(v or "").strip()
            if not sv or sv in seen:
                continue
            seen.add(sv)
            ordered.append(sv)
    return ordered


def _project_selected_design_code() -> str:
    """Single source: ``config/project/piping_design_codes.json`` → ``selected``."""
    raw = config.config_manager.get("piping_design_codes.selected", "")
    return str(raw or "").strip()


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
) -> NamedSizeTable | None:
    return run_size_matrix_editor(parent, title, table, pair_kind)


def _manage_named_tables(
    parent: tk.Toplevel,
    title: str,
    tables: list[NamedSizeTable],
    bundle: ClassLevelBundle,
    *,
    pair_kind: Literal["reducing", "branch"],
    refresh_dropdowns: Callable[[], None],
) -> None:
    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("420x320")
    win.transient(parent)

    shell = tk.Frame(win, highlightthickness=1, highlightbackground="#b0b0b0", highlightcolor="#b0b0b0", bg="#fafafa")
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
        name = simpledialog.askstring("Add table", "Table_Code (unique name):", parent=win)
        if not name or not name.strip():
            return
        name = name.strip()
        if name in _all_codes(bundle):
            messagebox.showerror("Duplicate", f"The name {name!r} is already in use.", parent=win)
            return
        nt = NamedSizeTable(name, [])
        tables.append(nt)
        refill()
        lb.selection_clear(0, "end")
        lb.selection_set(len(tables) - 1)
        edited = _edit_size_table_dialog(parent, f"Edit table — {name}", nt, pair_kind)
        if edited:
            tables[-1] = edited
        else:
            tables.pop()
            refill()
        refresh_dropdowns()

    def edit_table() -> None:
        sel = lb.curselection()
        if not sel:
            messagebox.showinfo("Selection", "Select a table to edit.", parent=win)
            return
        idx = int(sel[0])
        tbl = tables[idx]
        edited = _edit_size_table_dialog(parent, f"Edit table — {tbl.table_code}", tbl, pair_kind)
        if edited:
            tables[idx] = edited
            refill()
        refresh_dropdowns()

    def del_table() -> None:
        sel = lb.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if messagebox.askyesno("Delete", "Delete this table?", parent=win):
            tables.pop(idx)
            refill()
            refresh_dropdowns()

    bf = ttk.Frame(win)
    bf.pack(fill="x", padx=8, pady=(0, 8))
    ttk.Button(bf, text="Add", command=add_table).pack(side="left", padx=4)
    ttk.Button(bf, text="Edit", command=edit_table).pack(side="left", padx=4)
    ttk.Button(bf, text="Delete", command=del_table).pack(side="left", padx=4)
    ttk.Button(bf, text="Close", command=win.destroy).pack(side="right", padx=4)


class ClassLevelWizard(tk.Toplevel):
    def __init__(self, parent: tk.Tk, initial_bundle: ClassLevelBundle | None = None) -> None:
        super().__init__(parent)
        self.title("Class-level template data")
        self.geometry("920x620")
        self.transient(parent)
        self.grab_set()
        self.result: ClassLevelBundle | None = None
        self._fixed_design_code = _project_selected_design_code()
        self._material_combo_values = ["", *class_base_material_group_keys()]
        self._rating_combo_values = ["", *flange_pt_class_rating_options()]
        self._last_shown_class_idx: int | None = None

        merged = config.config_manager.merged()
        self._corrosion_default_value = str(
            config.config_manager.get("validation_policy.corrosion_allowance.default_value", "0.0")
            or "0.0"
        ).strip() or "0.0"
        self._corrosion_unit_symbol = _corrosion_allowance_unit_symbol(
            _project_selected_unit_system(merged)
        )
        self._corrosion_combo_values = _corrosion_reference_values(merged)
        _dt, _dp = read_design_units_from_merged(merged)
        self._class_define_headers = class_define_headers(_dt, _dp)
        self._fluid_service_headers = fluid_service_headers(_dt, _dp)
        self._class_design_temp_u, self._class_design_press_u = _dt, _dp
        (
            self._class_temp_from_h,
            self._class_temp_to_h,
            self._class_press_from_h,
            self._class_press_to_h,
        ) = ClassLevelWizard._resolve_temperature_pressure_header_keys(self._class_define_headers)
        if initial_bundle is None:
            blank = row_dict_for_headers(self._class_define_headers)
            self._bundle = ClassLevelBundle(
                class_define_rows=[
                    {
                        **blank,
                        "Design_Code": self._fixed_design_code,
                        _CORROSION_ALLOWANCE_KEY: self._corrosion_default_value,
                    }
                ],
                fluid_service_rows=[],
                joint_rows=[],
                schedule_rows=[],
                reducing_tables=[],
                branch_tables=[],
            )
        else:
            self._bundle = copy.deepcopy(initial_bundle)
            if not self._bundle.class_define_rows:
                blank = row_dict_for_headers(self._class_define_headers)
                self._bundle.class_define_rows = [{**blank, "Design_Code": self._fixed_design_code}]
            for row in self._bundle.class_define_rows:
                row["Design_Code"] = self._fixed_design_code
                if not str(row.get(_CORROSION_ALLOWANCE_KEY, "") or "").strip():
                    row[_CORROSION_ALLOWANCE_KEY] = self._corrosion_default_value

        nominal_mode = str(
            config.config_manager.get("units_notation.nominal_size.selected", "NPS") or "NPS"
        )
        self._size_catalog_all: list[str] = list(config.catalog_sizes_all(nominal_mode))
        self._size_catalog_preferred: set[str] = set(config.catalog_sizes_preferred(nominal_mode))
        self._size_nominal_mode: str = "DN" if str(nominal_mode).strip().upper() == "DN" else "NPS"
        self._sync_size_ranges_to_classes()

        _configure_sheet_treeview_style()

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self._schedule_refresh_class_list: Callable[[], None] = lambda: None
        self._size_range_refresh_class_list: Callable[[], None] = lambda: None
        self._tab_class(nb)
        self._tab_sheet(nb, "Fluid_Service", self._fluid_service_headers, "fluid")
        self._tab_sheet(nb, "Joint", JOINT_HEADERS, "joint")
        self._tab_size_range(nb)
        self._tab_schedule(nb)

        bf = ttk.Frame(self)
        bf.pack(fill="x", padx=8, pady=8)
        ttk.Button(bf, text="OK — build template", command=self._on_ok).pack(side="right", padx=6)
        ttk.Button(bf, text="Cancel", command=self._on_cancel).pack(side="right", padx=6)

    def _sync_size_ranges_to_classes(self) -> None:
        """class_define_rows 의 Class_Name 세트에 맞춰 size_ranges 를 재정렬/채움.
        신규 Class 는 선호 사이즈만 활성화된 기본값으로 seed. 사라진 Class 의 엔트리는 제거.
        """
        current_names = [
            (r.get("Class_Name") or "").strip()
            for r in self._bundle.class_define_rows
        ]
        existing_by_name: dict[str, ClassSizeRange] = {}
        for sr in self._bundle.size_ranges:
            key = (sr.class_name or "").strip()
            if key:
                existing_by_name[key] = sr

        preferred_default = [
            s for s in self._size_catalog_all if s in self._size_catalog_preferred
        ]
        new_ranges: list[ClassSizeRange] = []
        for name in current_names:
            if not name:
                continue
            existing = existing_by_name.get(name)
            if existing is not None:
                active = [s for s in existing.active_sizes if s in self._size_catalog_all]
                if not active:
                    active = list(preferred_default)
                new_ranges.append(ClassSizeRange(class_name=name, active_sizes=active))
            else:
                new_ranges.append(
                    ClassSizeRange(class_name=name, active_sizes=list(preferred_default))
                )
        self._bundle.size_ranges = new_ranges

    def _rename_size_range_class(self, old_name: str, new_name: str) -> None:
        old = (old_name or "").strip()
        new = (new_name or "").strip()
        if not old or not new or old == new:
            return
        for sr in self._bundle.size_ranges:
            if (sr.class_name or "").strip() == old:
                sr.class_name = new
                break

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
        old_name = (row.get("Class_Name") or "").strip()
        new_name = name_var.get() or ""
        row["Class_Name"] = new_name
        self._rename_size_range_class(old_name, new_name)
        self._sync_size_ranges_to_classes()
        self._refresh_class_listbox()
        self._class_list.selection_clear(0, "end")
        self._class_list.selection_set(idx)
        self._class_list.activate(idx)
        self._class_list.see(idx)
        _listbox_apply_stripes(self._class_list)

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
        ttk.Separator(lf, orient="horizontal").pack(fill="x", pady=(6, 4))
        ttk.Button(
            lf,
            text="Manage reducing tables…",
            command=self._open_reducing_manager,
        ).pack(fill="x", pady=2)
        ttk.Button(
            lf,
            text="Manage branch tables…",
            command=self._open_branch_manager,
        ).pack(fill="x", pady=2)

        rf = ttk.LabelFrame(tab, text="Selected row")
        rf.pack(side="left", fill="both", expand=True, padx=8, pady=4)
        self._class_entries: dict[str, tk.StringVar] = {}
        self._class_combos: dict[str, ttk.Combobox] = {}
        rows_f = ttk.Frame(rf)
        rows_f.pack(fill="both", expand=True)

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
                dc_text = self._fixed_design_code or "(piping_design_codes.selected is empty)"
                ttk.Label(rows_f, text=dc_text, width=44, anchor="w").grid(
                    row=grid_row, column=1, sticky="ew", pady=1, padx=px
                )
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

        self._refresh_class_listbox()
        if self._bundle.class_define_rows:
            self._class_list.selection_set(0)
            self._class_list.activate(0)
            self._class_list.see(0)
            self._class_list.focus_set()
            self._load_class_detail()

    def _refresh_combo_lists(self) -> None:
        rvals = list(self._reducing_names())
        bvals = list(self._branch_names())
        for h, widget in self._class_combos.items():
            if h in ("Branch_Table_1", "Branch_Table_2"):
                widget["values"] = bvals
            elif h in ("Reducing_Table_1", "Reducing_Table_2"):
                widget["values"] = rvals

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
        row["Design_Code"] = self._fixed_design_code
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
        row["Design_Code"] = self._fixed_design_code
        for h, v in self._class_entries.items():
            v.set(row.get(h, ""))
        for h, cb in self._class_combos.items():
            cb.set(row.get(h, ""))
        self._last_shown_class_idx = idx

    def _add_class_row(self) -> None:
        self._save_class_detail_to_row()
        nr = row_dict_for_headers(self._class_define_headers)
        nr["Design_Code"] = self._fixed_design_code
        nr[_CORROSION_ALLOWANCE_KEY] = self._corrosion_default_value
        self._bundle.class_define_rows.append(nr)
        self._sync_size_ranges_to_classes()
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
            self._sync_size_ranges_to_classes()
            self._last_shown_class_idx = None
            self._refresh_class_listbox()
            self._class_list.selection_set(min(idx, len(self._bundle.class_define_rows) - 1))
            self._load_class_detail()

    def _tab_sheet(self, nb: ttk.Notebook, title: str, headers: list[str], key: str) -> None:
        tab = ttk.Frame(nb)
        nb.add(tab, text=title)

        cols = tuple(headers)
        data_area = ttk.Frame(tab)
        data_area.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        data_area.grid_rowconfigure(0, weight=1)
        data_area.grid_columnconfigure(0, weight=1)

        tree_holder = ttk.Frame(data_area)
        tree_holder.grid_rowconfigure(0, weight=1)
        tree_holder.grid_columnconfigure(0, weight=1)

        tree = ttk.Treeview(
            tree_holder,
            columns=cols,
            show="headings",
            height=16,
            style="WizardSheet.Treeview",
        )
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=100)
        sy = ttk.Scrollbar(tree_holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sy.set)
        tree.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        tree_holder.grid(row=0, column=0, sticky="nsew")
        _tree_setup_tags(tree)

        empty_msg = f'No {title} rows yet. Use "Add row".'
        empty_ph = _canvas_dashed_empty_state(data_area, empty_msg, height=200, bg="#fafafa")
        empty_ph.grid(row=0, column=0, sticky="nsew")
        empty_ph.grid_remove()

        if key == "fluid":
            rows_attr = "fluid_service_rows"
        elif key == "joint":
            rows_attr = "joint_rows"
        else:
            rows_attr = "schedule_rows"

        def get_rows() -> list[dict[str, str]]:
            return getattr(self._bundle, rows_attr)

        def refill(sel_idx: int | None = None) -> None:
            for iid in tree.get_children():
                tree.delete(iid)
            rows = get_rows()
            for idx, r in enumerate(rows):
                tree.insert(
                    "",
                    "end",
                    values=tuple(r.get(h, "") for h in headers),
                    tags=_tree_row_tags(idx),
                )
            kids = tree.get_children()
            if rows:
                empty_ph.grid_remove()
                tree_holder.grid(row=0, column=0, sticky="nsew")
                pick = 0
                if sel_idx is not None and 0 <= sel_idx < len(kids):
                    pick = sel_idx
                if kids:
                    target = kids[pick]
                    tree.selection_set(target)
                    tree.focus(target)
                    tree.see(target)
            else:
                tree_holder.grid_remove()
                empty_ph.grid(row=0, column=0, sticky="nsew")

        refill()

        def add_row() -> None:
            get_rows().append(row_dict_for_headers(headers))
            refill(sel_idx=len(get_rows()) - 1)

        def edit_row() -> None:
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Selection", "Select a row to edit.", parent=self)
                return
            idx = tree.index(sel[0])
            cur = get_rows()[idx]
            new = _edit_row_dict_dialog(self, f"{title} 행 편집", headers, cur)
            if new:
                get_rows()[idx] = new
                refill(sel_idx=idx)

        def del_row() -> None:
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            get_rows().pop(idx)
            n = len(get_rows())
            refill(sel_idx=min(idx, n - 1) if n else None)

        ttk.Separator(tab, orient="horizontal").pack(fill="x", padx=8, pady=(4, 0))
        bf = ttk.Frame(tab)
        bf.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(bf, text="Add row", command=add_row).pack(side="left", padx=4)
        ttk.Button(bf, text="Edit row", command=edit_row).pack(side="left", padx=4)
        ttk.Button(bf, text="Delete row", command=del_row).pack(side="left", padx=4)

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

        def refill_class_list() -> None:
            nonlocal class_items
            class_items = build_class_items()
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
            for vis_idx, (src_idx, row) in enumerate(pairs):
                iid = f"r{src_idx}"
                tree.insert(
                    "",
                    "end",
                    iid=iid,
                    values=(
                        row.get("Size_From", ""),
                        row.get("Size_To", ""),
                        row.get("Schedule", ""),
                    ),
                    tags=_tree_row_tags(vis_idx),
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
            else:
                ent.insert(0, initial)
            ent.focus_set()
            if first_char is None:
                ent.selection_range(0, tk.END)

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

            if col_id == "#3":
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

                def move_by_wheel(e: tk.Event) -> str:
                    values = list(schedule_values)
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
                # Enter in dropdown → ComboboxSelected fires; move to next cell.
                cb.bind("<Return>", lambda _e: "break" if do_commit(1) else "break")
                cb.bind("<Down>", on_up_or_down)
                cb.bind("<KeyPress-Down>", on_up_or_down, add="+")
                cb.bind("<KP_Down>", on_up_or_down, add="+")
                cb.bind("<Up>", on_up_or_down)
                cb.bind("<KeyPress-Up>", on_up_or_down, add="+")
                cb.bind("<KP_Up>", on_up_or_down, add="+")
                cb.bind("<Left>", consume_key)
                cb.bind("<Right>", consume_key)
                cb.bind("<MouseWheel>", move_by_wheel)
                cb.bind("<Button-4>", move_by_wheel)
                cb.bind("<Button-5>", move_by_wheel)
                # Item clicked in dropdown list.
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

        self._schedule_refresh_class_list = refill_class_list
        refill_class_list()

    def _open_reducing_manager(self) -> None:
        self._save_class_detail_to_row()

        def refresh() -> None:
            self._refresh_combo_lists()
            self._load_class_detail()

        _manage_named_tables(
            self,
            "Reducing tables (sheet: Reducing_Table)",
            self._bundle.reducing_tables,
            self._bundle,
            pair_kind="reducing",
            refresh_dropdowns=refresh,
        )

    def _open_branch_manager(self) -> None:
        self._save_class_detail_to_row()

        def refresh() -> None:
            self._refresh_combo_lists()
            self._load_class_detail()

        _manage_named_tables(
            self,
            "Branch tables (sheet: Branch_Table)",
            self._bundle.branch_tables,
            self._bundle,
            pair_kind="branch",
            refresh_dropdowns=refresh,
        )

    def _tab_size_range(self, nb: ttk.Notebook) -> None:
        """Class 별 활성 Size Range 편집 탭 (Class Constraint — Size Range)."""
        tab = ttk.Frame(nb)
        nb.add(tab, text="Size Range")

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
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        header = ttk.Frame(right)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        mode_label = ttk.Label(
            header,
            text=(
                f"Nominal size mode: {self._size_nominal_mode}  |  "
                "Preferred sizes are pre-checked. Check non-preferred sizes only when actually required."
            ),
        )
        mode_label.pack(anchor="w")

        btns = ttk.Frame(right)
        btns.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        scroll_host = ttk.Frame(right)
        scroll_host.grid(row=1, column=0, sticky="nsew")
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
            canvas.itemconfigure(canvas_window, width=canvas.winfo_width())

        grid_frame.bind("<Configure>", _on_grid_config)
        canvas.bind("<Configure>", _on_grid_config)

        state: dict[str, object] = {
            "class_name": "",
            "vars": {},  # size -> tk.BooleanVar
        }

        def _selected_class_name() -> str:
            sel = class_lb.curselection()
            if not sel:
                return ""
            idx = int(sel[0])
            if 0 <= idx < len(self._bundle.class_define_rows):
                return (
                    self._bundle.class_define_rows[idx].get("Class_Name") or ""
                ).strip()
            return ""

        def _refresh_class_list() -> None:
            class_lb.delete(0, "end")
            for row in self._bundle.class_define_rows:
                class_lb.insert("end", (row.get("Class_Name") or "").strip() or "(unnamed)")
            _listbox_apply_stripes(class_lb)

        def _find_range_entry(name: str) -> ClassSizeRange | None:
            n = (name or "").strip()
            for sr in self._bundle.size_ranges:
                if (sr.class_name or "").strip() == n:
                    return sr
            return None

        def _persist_current() -> None:
            name = str(state.get("class_name") or "")
            vars_map: dict[str, tk.BooleanVar] = state.get("vars", {})  # type: ignore[assignment]
            if not name or not vars_map:
                return
            active = [s for s in self._size_catalog_all if bool(vars_map.get(s) and vars_map[s].get())]
            entry = _find_range_entry(name)
            if entry is None:
                self._bundle.size_ranges.append(
                    ClassSizeRange(class_name=name, active_sizes=active)
                )
            else:
                entry.active_sizes = active

        def _render_for_class(name: str) -> None:
            for child in list(grid_frame.winfo_children()):
                child.destroy()
            state["class_name"] = name
            state["vars"] = {}
            if not name:
                ttk.Label(
                    grid_frame,
                    text="Select a class on the left to edit its Size Range.",
                ).grid(row=0, column=0, padx=6, pady=6, sticky="w")
                _on_grid_config()
                return

            entry = _find_range_entry(name)
            active_set = set(entry.active_sizes) if entry is not None else set(
                self._size_catalog_preferred
            )

            vars_map: dict[str, tk.BooleanVar] = {}
            cols = 8
            r = 0
            c = 0

            def _make_toggle(size: str) -> Callable[[], None]:
                def _cb() -> None:
                    _persist_current()
                return _cb

            for size in self._size_catalog_all:
                is_preferred = size in self._size_catalog_preferred
                label = f"{size}" + ("" if is_preferred else "  *")
                var = tk.BooleanVar(value=(size in active_set))
                vars_map[size] = var
                cb = ttk.Checkbutton(
                    grid_frame, text=label, variable=var, command=_make_toggle(size)
                )
                cb.grid(row=r, column=c, padx=8, pady=2, sticky="w")
                c += 1
                if c >= cols:
                    c = 0
                    r += 1

            state["vars"] = vars_map
            _on_grid_config()

        def _on_class_select(_e=None) -> None:
            _persist_current()
            name = _selected_class_name()
            _render_for_class(name)

        class_lb.bind("<<ListboxSelect>>", _on_class_select)

        def _set_all_preferred_only() -> None:
            name = _selected_class_name()
            if not name:
                return
            for size, var in (state.get("vars") or {}).items():  # type: ignore[union-attr]
                var.set(size in self._size_catalog_preferred)
            _persist_current()

        def _select_all() -> None:
            name = _selected_class_name()
            if not name:
                return
            for size, var in (state.get("vars") or {}).items():  # type: ignore[union-attr]
                var.set(True)
            _persist_current()

        def _clear_all_non_preferred() -> None:
            name = _selected_class_name()
            if not name:
                return
            for size, var in (state.get("vars") or {}).items():  # type: ignore[union-attr]
                if size not in self._size_catalog_preferred:
                    var.set(False)
            _persist_current()

        ttk.Button(btns, text="Defaults (preferred only)", command=_set_all_preferred_only).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(btns, text="Select all", command=_select_all).pack(side="left", padx=(0, 6))
        ttk.Button(
            btns, text="Clear non-preferred", command=_clear_all_non_preferred
        ).pack(side="left", padx=(0, 6))

        def _refresh() -> None:
            _persist_current()
            self._sync_size_ranges_to_classes()
            _refresh_class_list()
            if self._bundle.class_define_rows:
                class_lb.selection_clear(0, "end")
                class_lb.selection_set(0)
                _on_class_select()
            else:
                _render_for_class("")

        self._size_range_refresh_class_list = _refresh
        _refresh()

    def _on_ok(self) -> None:
        idx = self._current_class_idx()
        if idx is not None:
            self._save_class_row_at_index(idx)
        self._size_range_refresh_class_list()  # persist current edits first
        self._sync_size_ranges_to_classes()
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
