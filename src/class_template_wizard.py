"""Class-level template wizard (English UI) — runs before template xlsx is built."""

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable, Literal

import config
from class_level_model import ClassLevelBundle, NamedSizeTable, row_dict_for_headers
from class_spec import class_base_material_group_keys, flange_pt_class_rating_options
from size_matrix_editor import run_size_matrix_editor
from template_generator import (
    CLASS_DEFINE_HEADERS,
    FLUID_SERVICE_HEADERS,
    JOINT_HEADERS,
    SCHEDULE_HEADERS,
)

# Light-theme list / sheet visuals (zebra ≈ thin row separation)
_STRIPE_A = "#ffffff"
_STRIPE_B = "#f0f1f4"
_LIST_HOVER = "#dceaf7"


def _project_selected_design_code() -> str:
    """Single source: ``config/project/piping_design_codes.json`` → ``selected``."""
    raw = config.config_manager.get("piping_design_codes.selected", "")
    return str(raw or "").strip()


def _default_bundle() -> ClassLevelBundle:
    blank_class = row_dict_for_headers(CLASS_DEFINE_HEADERS)
    blank_class["Design_Code"] = _project_selected_design_code()
    return ClassLevelBundle(
        class_define_rows=[blank_class],
        fluid_service_rows=[],
        joint_rows=[],
        schedule_rows=[],
        reducing_tables=[],
        branch_tables=[],
    )


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
    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("Class-level template data")
        self.geometry("920x620")
        self.transient(parent)
        self.grab_set()
        self.result: ClassLevelBundle | None = None
        self._bundle = _default_bundle()
        self._fixed_design_code = _project_selected_design_code()
        self._material_combo_values = ["", *class_base_material_group_keys()]
        self._rating_combo_values = ["", *flange_pt_class_rating_options()]
        self._last_shown_class_idx: int | None = None

        _configure_sheet_treeview_style()

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self._tab_class(nb)
        self._tab_sheet(nb, "Fluid_Service", FLUID_SERVICE_HEADERS, "fluid")
        self._tab_sheet(nb, "Joint", JOINT_HEADERS, "joint")
        self._tab_sheet(nb, "Schedule", SCHEDULE_HEADERS, "schedule")

        bt = ttk.Frame(self)
        bt.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(
            bt,
            text="Manage reducing tables…",
            command=self._open_reducing_manager,
        ).pack(side="left", padx=4)
        ttk.Button(
            bt,
            text="Manage branch tables…",
            command=self._open_branch_manager,
        ).pack(side="left", padx=4)

        bf = ttk.Frame(self)
        bf.pack(fill="x", padx=8, pady=8)
        ttk.Button(bf, text="OK — build template", command=self._on_ok).pack(side="right", padx=6)
        ttk.Button(bf, text="Cancel", command=self._on_cancel).pack(side="right", padx=6)

    def _reducing_names(self) -> tuple[str, ...]:
        return ("", *tuple(t.table_code.strip() for t in self._bundle.reducing_tables if t.table_code.strip()))

    def _branch_names(self) -> tuple[str, ...]:
        return ("", *tuple(t.table_code.strip() for t in self._bundle.branch_tables if t.table_code.strip()))

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

        rf = ttk.LabelFrame(tab, text="Selected row")
        rf.pack(side="left", fill="both", expand=True, padx=8, pady=4)
        self._class_entries: dict[str, tk.StringVar] = {}
        self._class_combos: dict[str, ttk.Combobox] = {}
        rows_f = ttk.Frame(rf)
        rows_f.pack(fill="both", expand=True)
        for i, h in enumerate(CLASS_DEFINE_HEADERS):
            ttk.Label(rows_f, text=h, width=22).grid(row=i, column=0, sticky="w", pady=1)
            if h == "Design_Code":
                dc_text = self._fixed_design_code or "(piping_design_codes.selected is empty)"
                ttk.Label(rows_f, text=dc_text, width=44, anchor="w").grid(
                    row=i, column=1, sticky="ew", pady=1
                )
            elif h == "Class_Base_Material":
                cb = ttk.Combobox(
                    rows_f,
                    width=42,
                    state="readonly",
                    values=self._material_combo_values,
                )
                cb.grid(row=i, column=1, sticky="ew", pady=1)
                self._class_combos[h] = cb
            elif h == "Class_Rating":
                cb = ttk.Combobox(
                    rows_f,
                    width=42,
                    state="readonly",
                    values=self._rating_combo_values,
                )
                cb.grid(row=i, column=1, sticky="ew", pady=1)
                self._class_combos[h] = cb
            elif h in ("Branch_Table_1", "Branch_Table_2"):
                cb = ttk.Combobox(rows_f, width=42, state="readonly", values=list(self._branch_names()))
                cb.grid(row=i, column=1, sticky="ew", pady=1)
                self._class_combos[h] = cb
            elif h in ("Reducing_Table_1", "Reducing_Table_2"):
                cb = ttk.Combobox(rows_f, width=42, state="readonly", values=list(self._reducing_names()))
                cb.grid(row=i, column=1, sticky="ew", pady=1)
                self._class_combos[h] = cb
            else:
                v = tk.StringVar()
                e = ttk.Entry(rows_f, textvariable=v, width=44)
                e.grid(row=i, column=1, sticky="ew", pady=1)
                self._class_entries[h] = v
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
        nr = row_dict_for_headers(CLASS_DEFINE_HEADERS)
        nr["Design_Code"] = self._fixed_design_code
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

    def _on_ok(self) -> None:
        idx = self._current_class_idx()
        if idx is not None:
            self._save_class_row_at_index(idx)
        errs = self._bundle.validate()
        if errs:
            messagebox.showerror("Validation", "\n".join(errs), parent=self)
            return
        self.result = copy.deepcopy(self._bundle)
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()


def run_class_level_wizard(parent: tk.Tk) -> ClassLevelBundle | None:
    dlg = ClassLevelWizard(parent)
    parent.wait_window(dlg)
    return dlg.result
