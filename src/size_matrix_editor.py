"""Matrix editor for reducing/branch size tables (Excel-like: browse + F2/edit + Ctrl+click)."""

from __future__ import annotations

from tkinter import messagebox
from typing import Literal

import tkinter as tk
from tkinter import ttk

import config
from class_level_model import NamedSizeTable, SizeTableRow
from size_matrix_common import (
    BRANCH_ITEM_TYPES_OK,
    MIN_REDUCING_SIZE1_NPS,
    REDUCING_ITEM_TYPES_OK,
    axes_from_rows,
    cell_allowed,
    load_axis_allowlist,
    matrix_help_text,
    normalize_nominal_mode,
    size_number,
    sorted_nominal_master_list,
)
from size_matrix_edit_ops import MatrixEditOpsMixin


class MatrixTableDialog(MatrixEditOpsMixin, tk.Toplevel):
    """
    Rows = Size1, columns = Size2; titles on dedicated header row/column.
    Selection is clamped to editable (label) cells only.
    """

    GRID_DATA_ROW0 = 2

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        table: NamedSizeTable,
        pair_kind: Literal["reducing", "branch"],
        nominal_mode: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self._own_grab = False
        try:
            self.grab_set()
            self._own_grab = True
        except tk.TclError:
            pass
        try:
            self.resizable(True, True)
        except tk.TclError:
            pass
        self._pair_kind = pair_kind
        self._table_code = table.table_code.strip()
        self._nominal_mode = normalize_nominal_mode(nominal_mode)
        self._allowed_sizes = load_axis_allowlist(self._nominal_mode)
        base1, base2 = axes_from_rows(table.rows, pair_kind, self._nominal_mode)
        self._nominal_master = sorted_nominal_master_list(self._nominal_mode)
        extra_sizes = {s for s in base1} | {s for s in base2}
        if self._nominal_master:
            axis_set = sorted(
                set(self._nominal_master) | extra_sizes,
                key=size_number,
            )
            self._nominal_dialog_rows = list(self._nominal_master)
        else:
            axis_set = sorted(set(base1) | set(base2), key=size_number)
            self._nominal_dialog_rows = list(axis_set)
        self._axis_master: list[str] = list(axis_set)

        self._values: dict[tuple[str, str], str] = {}
        for r in table.rows:
            k = (r.size1.strip(), r.size2.strip())
            if r.item_type.strip():
                self._values[k] = r.item_type.strip().upper()

        preferred = set(config.catalog_sizes_preferred(self._nominal_mode))
        sizes_in_data_1 = {r.size1.strip() for r in table.rows if r.size1.strip()}
        sizes_in_data_2 = {r.size2.strip() for r in table.rows if r.size2.strip()}
        self._axis_enabled_size1: dict[str, bool] = {
            s: (s in preferred) or (s in sizes_in_data_1) for s in self._axis_master
        }
        self._axis_enabled_size2: dict[str, bool] = {
            s: (s in preferred) or (s in sizes_in_data_2) for s in self._axis_master
        }
        self._recompute_displayed_axes()

        self._labels: dict[tuple[int, int], tk.Label] = {}
        self._anchor_rc: tuple[int, int] | None = None
        self._focus_rc: tuple[int, int] | None = None
        self._selected_cells: set[tuple[int, int]] = set()
        self._edit_entry: tk.Entry | None = None
        self._edit_rc: tuple[int, int] | None = None
        self._result: NamedSizeTable | None = None
        self._inner_keybindings_done = False
        self._inner_pointer_binds_done = False
        self._widget_to_rc: dict[tk.Misc, tuple[int, int]] = {}
        self._drag_mode: str | None = None
        self._drag_start_rc: tuple[int, int] | None = None
        self._drag_snap: frozenset[tuple[int, int]] | None = None
        self._drag_mouse_moved = False
        self._drag_last_rc: tuple[int, int] | None = None

        self.geometry("960x640")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        ttk.Label(top, text=f"Table: {self._table_code}", font=("", 11, "bold")).pack(
            side="left", padx=(0, 12)
        )
        ttk.Button(top, text="Help", command=self._show_help).pack(side="left")

        tb = ttk.Frame(self)
        tb.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        tb.rowconfigure(0, weight=1)
        tb.columnconfigure(0, weight=1)

        canvas = tk.Canvas(tb, highlightthickness=0)
        self._matrix_canvas = canvas
        vsb = ttk.Scrollbar(tb, orient="vertical", command=canvas.yview)
        hsb = ttk.Scrollbar(tb, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tb.columnconfigure(0, weight=1)
        tb.rowconfigure(0, weight=1)

        inner = ttk.Frame(canvas)
        self._inner = inner
        inner.configure(takefocus=True)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        def _cfg_scroll(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", _cfg_scroll)

        def _mw(_e):
            canvas.yview_scroll(int(-1 * (_e.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _mw)
        inner.bind("<MouseWheel>", _mw)

        self._build_grid(inner)
        self._ensure_inner_keybindings()

        ax = ttk.Frame(self)
        ax.grid(row=2, column=0, sticky="ew", padx=4, pady=2)
        ttk.Button(ax, text="Edit Size", command=self._open_edit_size_dialog).pack(
            side="left", padx=2
        )
        ttk.Button(ax, text="Reset", command=self._reset_template).pack(side="left", padx=8)

        bf = ttk.Frame(self)
        bf.grid(row=3, column=0, pady=8)
        ttk.Button(bf, text="OK", command=self._on_ok).pack(side="left", padx=6)
        ttk.Button(bf, text="Cancel", command=self._on_cancel).pack(side="left", padx=6)

        self.protocol("WM_DELETE_WINDOW", lambda: self._on_cancel())
        self.after(80, lambda: self._inner.focus_set())

    def _recompute_displayed_axes(self) -> None:
        """표시할 행/열 축을 enabled 플래그 기준으로 재계산."""
        self._size1_rows = [s for s in self._axis_master if self._axis_enabled_size1.get(s, False)]
        self._size2_cols = [s for s in self._axis_master if self._axis_enabled_size2.get(s, False)]

    def _row_axis_title(self) -> str:
        return "Header size" if self._pair_kind == "branch" else "Main Size"

    def _col_axis_title(self) -> str:
        return "Branch Size" if self._pair_kind == "branch" else "Reducing Size"

    def _edit_size_col_headers(self) -> tuple[str, str]:
        if self._pair_kind == "branch":
            return ("Size1 (Header)", "Size2 (Branch)")
        return ("Size1 (Main)", "Size2 (Reducing)")

    def _open_edit_size_dialog(self) -> None:
        self._end_edit(commit=True)
        win = tk.Toplevel(self)
        win.title("Edit Size")
        win.transient(self)
        had_grab = self._own_grab
        if had_grab:
            try:
                self.grab_release()
            except tk.TclError:
                pass
        try:
            win.grab_set()
        except tk.TclError:
            pass

        def dismiss() -> None:
            try:
                win.grab_release()
            except tk.TclError:
                pass
            try:
                win.destroy()
            except tk.TclError:
                pass
            if had_grab and self.winfo_exists():
                try:
                    self.grab_set()
                except tk.TclError:
                    pass

        outer = ttk.Frame(win, padding=8)
        outer.pack(fill="both", expand=True)
        h1, h2 = self._edit_size_col_headers()
        ttk.Label(
            outer,
            text=(
                f"One row per {self._nominal_mode} from the standard catalog. "
                f"Checkboxes turn that label on or off for the matrix row axis ({h1}) "
                f"and column axis ({h2}). Unchecked greys the whole row or column."
            ),
            wraplength=560,
        ).pack(anchor="w", pady=(0, 6))

        scroll_area = ttk.Frame(outer)
        scroll_area.pack(fill="both", expand=True)
        scroll_area.rowconfigure(0, weight=1)
        scroll_area.columnconfigure(0, weight=1)

        canvas = tk.Canvas(scroll_area, highlightthickness=0, height=420, width=520)
        vsb = ttk.Scrollbar(scroll_area, orient="vertical", command=canvas.yview)
        hsb = ttk.Scrollbar(scroll_area, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        grid_fr = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=grid_fr, anchor="nw")

        def _cfg_inner(_e=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all") or (0, 0, 0, 0))

        grid_fr.bind("<Configure>", _cfg_inner)

        canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        vars1: dict[str, tk.BooleanVar] = {}
        vars2: dict[str, tk.BooleanVar] = {}
        tk.Label(grid_fr, text=self._nominal_mode, width=8, font=("", 9, "bold")).grid(
            row=0, column=0, sticky="nsew", padx=2, pady=2
        )
        ttk.Label(grid_fr, text=h1, width=16).grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        ttk.Label(grid_fr, text=h2, width=18).grid(row=0, column=2, sticky="nsew", padx=2, pady=2)
        for ri, s in enumerate(self._nominal_dialog_rows):
            tk.Label(grid_fr, text=s, width=10, anchor="e").grid(
                row=ri + 1, column=0, sticky="nsew", padx=2, pady=1
            )
            v1 = tk.BooleanVar(value=self._axis_enabled_size1.get(s, False))
            v2 = tk.BooleanVar(value=self._axis_enabled_size2.get(s, False))
            vars1[s] = v1
            vars2[s] = v2
            ttk.Checkbutton(grid_fr, variable=v1).grid(row=ri + 1, column=1)
            ttk.Checkbutton(grid_fr, variable=v2).grid(row=ri + 1, column=2)

        bf = ttk.Frame(outer)
        bf.pack(pady=(10, 0))

        def on_ok() -> None:
            for s in self._nominal_dialog_rows:
                self._axis_enabled_size1[s] = bool(vars1[s].get())
                self._axis_enabled_size2[s] = bool(vars2[s].get())
            self._recompute_displayed_axes()
            self._rebuild_grid()
            dismiss()

        def on_cancel() -> None:
            dismiss()

        ttk.Button(bf, text="OK", command=on_ok).pack(side="left", padx=6)
        ttk.Button(bf, text="Cancel", command=on_cancel).pack(side="left", padx=6)
        win.protocol("WM_DELETE_WINDOW", on_cancel)

    def _show_help(self) -> None:
        win = tk.Toplevel(self)
        win.title("Matrix editor — Help")
        win.transient(self)
        txt = tk.Text(win, wrap="word", width=88, height=28, font=("Segoe UI", 10))
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", matrix_help_text(self._pair_kind, self._nominal_mode))
        txt.config(state="disabled")
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 8))

    def _item_ok(self, raw: str) -> bool:
        v = raw.strip().upper()
        if not v:
            return True
        if self._pair_kind == "branch":
            return v in BRANCH_ITEM_TYPES_OK
        return v in REDUCING_ITEM_TYPES_OK

    def _rect_cells_corners(self, a: tuple[int, int], b: tuple[int, int]) -> set[tuple[int, int]]:
        ar, ac = a
        br, bc = b
        r0, r1 = min(ar, br), max(ar, br)
        c0, c1 = min(ac, bc), max(ac, bc)
        return {
            (ri, ci)
            for ri in range(r0, r1 + 1)
            for ci in range(c0, c1 + 1)
            if (ri, ci) in self._labels
        }

    def _rc_at_root(self, x_root: int, y_root: int) -> tuple[int, int] | None:
        w = self.winfo_containing(x_root, y_root)
        while w is not None:
            rc = self._widget_to_rc.get(w)
            if rc is not None:
                return rc
            if w is self:
                break
            w = getattr(w, "master", None)
        return None

    def _toggle_ctrl_cell(self, ri: int, ci: int) -> None:
        if (ri, ci) not in self._labels:
            return
        if (ri, ci) in self._selected_cells:
            self._selected_cells.discard((ri, ci))
            if not self._selected_cells:
                self._selected_cells.add((ri, ci))
                self._focus_rc = (ri, ci)
            else:
                self._focus_rc = min(self._selected_cells)
        else:
            self._selected_cells.add((ri, ci))
            self._focus_rc = (ri, ci)
        self._anchor_rc = (ri, ci)
        self._clamp_anchor_focus()
        self._prune_selected_to_labels()

    def _clear_drag_state(self) -> None:
        self._drag_mode = None
        self._drag_start_rc = None
        self._drag_snap = None
        self._drag_mouse_moved = False
        self._drag_last_rc = None

    def _end_label_pointer_gesture(self, event: tk.Event | None) -> None:
        if self._drag_mode is None:
            return
        mode = self._drag_mode
        moved = self._drag_mouse_moved
        start = self._drag_start_rc
        fin: tuple[int, int] | None = None
        if event is not None:
            fin = self._rc_at_root(event.x_root, event.y_root)
        last = fin or self._drag_last_rc or start
        try:
            self._inner.grab_release()
        except tk.TclError:
            pass
        if mode == "ctrl" and not moved and start is not None:
            self._toggle_ctrl_cell(*start)
        elif moved and start is not None and last is not None:
            if mode == "replace":
                self._anchor_rc = start
                self._focus_rc = last
            elif mode == "ctrl":
                self._anchor_rc = start
                self._focus_rc = last
            elif mode == "shift":
                self._focus_rc = last
        self._clear_drag_state()
        self._clamp_anchor_focus()
        self._prune_selected_to_labels()
        self._refresh_all_cell_styles()

    def _on_label_b1_press(self, event: tk.Event, ri: int, ci: int) -> None:
        try:
            self._inner.grab_release()
        except tk.TclError:
            pass
        self._end_edit(commit=True)
        if (ri, ci) not in self._labels:
            return
        shift = bool(event.state & 0x0001)
        ctrl = bool(event.state & 0x0004)
        self._clear_drag_state()
        if ctrl:
            self._drag_mode = "ctrl"
            self._drag_snap = frozenset(self._selected_cells)
            self._drag_start_rc = (ri, ci)
            self._drag_last_rc = (ri, ci)
        elif shift and self._anchor_rc is not None:
            self._drag_mode = "shift"
            self._drag_snap = frozenset(self._selected_cells)
            self._drag_start_rc = (ri, ci)
            self._focus_rc = (ri, ci)
            self._selected_cells = set(self._drag_snap) | self._rect_cells_corners(
                self._anchor_rc, self._focus_rc
            )
            self._drag_last_rc = (ri, ci)
        else:
            self._drag_mode = "replace"
            self._drag_start_rc = (ri, ci)
            self._anchor_rc = self._focus_rc = (ri, ci)
            self._selected_cells = {(ri, ci)}
            self._drag_last_rc = (ri, ci)
        self._clamp_anchor_focus()
        self._prune_selected_to_labels()
        self._refresh_all_cell_styles()
        try:
            self._inner.grab_set()
        except tk.TclError:
            pass
        self._inner.focus_set()

    def _on_inner_b1_motion(self, event: tk.Event) -> None:
        if self._drag_mode is None or self._drag_start_rc is None:
            return
        cur = self._rc_at_root(event.x_root, event.y_root)
        if cur is None:
            return
        if cur != self._drag_start_rc:
            self._drag_mouse_moved = True
        self._drag_last_rc = cur
        if self._drag_mode == "replace":
            self._selected_cells = self._rect_cells_corners(self._drag_start_rc, cur)
            self._focus_rc = cur
        elif self._drag_mode == "ctrl":
            base = set(self._drag_snap) if self._drag_snap is not None else set()
            self._selected_cells = base | self._rect_cells_corners(self._drag_start_rc, cur)
            self._focus_rc = cur
        elif self._drag_mode == "shift" and self._anchor_rc is not None:
            self._focus_rc = cur
            base = set(self._drag_snap) if self._drag_snap is not None else set()
            self._selected_cells = base | self._rect_cells_corners(self._anchor_rc, cur)
        self._clamp_anchor_focus()
        self._prune_selected_to_labels()
        self._refresh_all_cell_styles()

    def _on_inner_b1_release(self, event: tk.Event) -> None:
        self._end_label_pointer_gesture(event)

    def _ensure_inner_pointer_bindings(self) -> None:
        if self._inner_pointer_binds_done:
            return
        inn = self._inner
        cv = getattr(self, "_matrix_canvas", None)
        inn.bind("<B1-Motion>", self._on_inner_b1_motion)
        inn.bind("<ButtonRelease-1>", self._on_inner_b1_release)
        self.bind("<B1-Motion>", self._on_inner_b1_motion)
        self.bind("<ButtonRelease-1>", self._on_inner_b1_release)
        if cv is not None and cv.winfo_exists():
            cv.bind("<B1-Motion>", self._on_inner_b1_motion)
            cv.bind("<ButtonRelease-1>", self._on_inner_b1_release)
        self._inner_pointer_binds_done = True

    def _prune_selected_to_labels(self) -> None:
        if not self._labels:
            self._selected_cells.clear()
            return
        self._selected_cells = {c for c in self._selected_cells if c in self._labels}
        if self._focus_rc and self._focus_rc in self._labels:
            if not self._selected_cells:
                self._selected_cells.add(self._focus_rc)
            elif self._focus_rc not in self._selected_cells:
                self._selected_cells.add(self._focus_rc)

    def _cell_display_bg(self, ri: int, ci: int) -> str:
        s1, s2 = self._key(ri, ci)
        val = self._values.get((s1, s2), "")
        ok = self._item_ok(val)
        in_sel = (ri, ci) in self._selected_cells
        if in_sel:
            return "#fff9c4" if ok else "#ffcc99"
        return "white" if ok else "#ffcccc"

    def _refresh_all_cell_styles(self) -> None:
        for (ri, ci), lb in self._labels.items():
            lb.config(bg=self._cell_display_bg(ri, ci))

    def _snap_to_label(self, r: int, c: int) -> tuple[int, int] | None:
        if not self._labels:
            return None
        if (r, c) in self._labels:
            return (r, c)
        best: tuple[int, int] | None = None
        bestd = 10**9
        for kr, kc in self._labels:
            d = abs(kr - r) + abs(kc - c)
            if d < bestd or (d == bestd and best and (kr, kc) < best):
                bestd = d
                best = (kr, kc)
        return best

    def _clamp_anchor_focus(self) -> None:
        if not self._labels:
            self._anchor_rc = self._focus_rc = None
            return
        keys = sorted(self._labels.keys(), key=lambda t: (t[0], t[1]))
        if self._focus_rc is not None:
            sn = self._snap_to_label(*self._focus_rc)
            self._focus_rc = sn if sn is not None else keys[0]
        if self._anchor_rc is not None:
            sn = self._snap_to_label(*self._anchor_rc)
            self._anchor_rc = sn if sn is not None else keys[0]
        else:
            self._anchor_rc = self._focus_rc
        if self._anchor_rc is None:
            self._anchor_rc = keys[0]
        if self._focus_rc is None:
            self._focus_rc = keys[0]

    def _ensure_inner_keybindings(self) -> None:
        if self._inner_keybindings_done:
            return
        inn = self._inner
        inn.bind("<F2>", lambda e: self._f2_edit())
        inn.bind("<Control-Return>", lambda e: self._ctrl_enter_fill())
        inn.bind("<Control-KeyPress>", self._on_control_keypress)
        for seq in ("<Up>", "<Down>", "<Left>", "<Right>"):
            inn.bind(seq, self._on_arrow)
        for seq in ("<Shift-Up>", "<Shift-Down>", "<Shift-Left>", "<Shift-Right>"):
            inn.bind(seq, self._on_shift_arrow)
        inn.bind("<Tab>", lambda e: self._tab_next(1))
        inn.bind("<Shift-Tab>", lambda e: self._tab_next(-1))
        inn.bind("<KeyPress>", self._on_browse_keypress)
        self._inner_keybindings_done = True

    def _on_control_keypress(self, event: tk.Event) -> str | None:
        k = event.keysym.lower()
        if k == "c":
            self._copy_selection()
            return "break"
        if k == "v":
            self._paste_at_focus()
            return "break"
        return None

    def _size1_at(self, ri: int) -> str:
        return self._size1_rows[ri]

    def _size2_at(self, ci: int) -> str:
        return self._size2_cols[ci]

    def _key(self, ri: int, ci: int) -> tuple[str, str]:
        return (self._size1_at(ri), self._size2_at(ci))

    def _rebuild_grid(self) -> None:
        self._end_edit(commit=False)
        try:
            self._inner.grab_release()
        except tk.TclError:
            pass
        self._clear_drag_state()
        self._widget_to_rc.clear()
        self._anchor_rc = self._focus_rc = None
        self._selected_cells.clear()
        for w in self._inner.winfo_children():
            w.destroy()
        self._labels.clear()
        self._build_grid(self._inner)
        self.update_idletasks()
        cv = getattr(self, "_matrix_canvas", None)
        if cv is not None and cv.winfo_exists():
            try:
                cv.configure(scrollregion=cv.bbox("all") or (0, 0, 0, 0))
            except tk.TclError:
                pass

    def _askyesno_modal(self, title: str, message: str) -> bool:
        """askyesno while this dialog uses grab_set() (nested modal on Windows)."""
        if self._own_grab:
            try:
                self.grab_release()
            except tk.TclError:
                pass
        try:
            return bool(messagebox.askyesno(title, message, parent=self))
        finally:
            if self._own_grab and self.winfo_exists():
                try:
                    self.grab_set()
                except tk.TclError:
                    pass

    def _build_grid(self, inner: ttk.Frame) -> None:
        n2 = len(self._size2_cols)
        n1 = len(self._size1_rows)
        gr0 = MatrixTableDialog.GRID_DATA_ROW0

        tk.Label(inner, text="", width=11, relief="ridge").grid(row=0, column=0, sticky="nsew")
        col_span = max(1, n2)
        tk.Label(
            inner,
            text=self._col_axis_title(),
            relief="ridge",
            anchor="center",
        ).grid(row=0, column=1, columnspan=col_span, sticky="nsew")

        tk.Label(inner, text=self._row_axis_title(), relief="ridge", anchor="center").grid(
            row=1, column=0, sticky="nsew"
        )
        for ci, s2 in enumerate(self._size2_cols):
            tk.Label(inner, text=s2, width=6, relief="ridge").grid(row=1, column=ci + 1, sticky="nsew")

        for ri, s1 in enumerate(self._size1_rows):
            tk.Label(inner, text=s1, width=13, relief="ridge").grid(
                row=gr0 + ri, column=0, sticky="nsew"
            )
            for ci, s2 in enumerate(self._size2_cols):
                allowed = cell_allowed(s1, s2, self._pair_kind)
                if not allowed:
                    tk.Label(inner, text="", width=6, relief="flat", bg="#e0e0e0").grid(
                        row=gr0 + ri, column=ci + 1, sticky="nsew"
                    )
                    continue
                key = (s1, s2)
                txt = self._values.get(key, "")
                lb = tk.Label(
                    inner,
                    text=txt,
                    width=7,
                    relief="ridge",
                    bg="white",
                    anchor="w",
                    padx=1,
                )
                lb.grid(row=gr0 + ri, column=ci + 1, sticky="nsew")
                self._labels[(ri, ci)] = lb
                self._widget_to_rc[lb] = (ri, ci)

                def _label_b1_press(e: tk.Event, r: int = ri, c: int = ci) -> None:
                    self._on_label_b1_press(e, r, c)

                def _label_b1_motion(e: tk.Event) -> None:
                    self._on_inner_b1_motion(e)

                def _label_b1_release(e: tk.Event) -> None:
                    self._on_inner_b1_release(e)

                lb.bind("<Button-1>", _label_b1_press)
                lb.bind("<B1-Motion>", _label_b1_motion)
                lb.bind("<ButtonRelease-1>", _label_b1_release)

        self._ensure_inner_keybindings()
        self._ensure_inner_pointer_bindings()
        self._refresh_all_cell_styles()

    def _ordered_keys(self) -> list[tuple[int, int]]:
        return sorted(self._labels.keys(), key=lambda t: (t[0], t[1]))

    def _tab_next(self, delta: int) -> str:
        self._end_edit(commit=True)
        keys = self._ordered_keys()
        if not keys:
            return "break"
        if self._focus_rc is None:
            self._anchor_rc = self._focus_rc = keys[0]
            self._selected_cells = {keys[0]}
            self._clamp_anchor_focus()
            self._refresh_all_cell_styles()
            self._inner.focus_set()
            return "break"
        if self._focus_rc not in keys:
            self._anchor_rc = self._focus_rc = keys[0]
            self._selected_cells = {keys[0]}
            self._clamp_anchor_focus()
            self._refresh_all_cell_styles()
            return "break"
        idx = keys.index(self._focus_rc)
        nxt = idx + (1 if delta > 0 else -1)
        if 0 <= nxt < len(keys):
            self._anchor_rc = self._focus_rc = keys[nxt]
            self._selected_cells = {keys[nxt]}
        self._clamp_anchor_focus()
        self._refresh_all_cell_styles()
        self._inner.focus_set()
        return "break"

    def _on_arrow(self, event: tk.Event) -> str:
        if self._edit_entry is not None:
            pos = self._edit_rc
            self._end_edit(commit=True)
            if pos:
                self._anchor_rc = self._focus_rc = pos
                self._selected_cells = {pos}
        else:
            self._end_edit(commit=True)
        sym = event.keysym
        if sym in ("Up", "Down", "Left", "Right"):
            self._arrow_move(sym)
        return "break"

    def _arrow_move(self, sym: str) -> None:
        if self._focus_rc is None:
            keys0 = self._ordered_keys()
            if keys0:
                self._anchor_rc = self._focus_rc = keys0[0]
                self._selected_cells = {keys0[0]}
                self._clamp_anchor_focus()
                self._refresh_all_cell_styles()
            self._inner.focus_set()
            return
        ri, ci = self._focus_rc
        if sym == "Up":
            nxt = self._move_same_col(ri, ci, -1)
        elif sym == "Down":
            nxt = self._move_same_col(ri, ci, 1)
        elif sym == "Left":
            nxt = self._move_same_row(ri, ci, -1)
        else:
            nxt = self._move_same_row(ri, ci, 1)
        if nxt:
            self._anchor_rc = self._focus_rc = nxt
            self._selected_cells = {nxt}
        self._clamp_anchor_focus()
        self._refresh_all_cell_styles()
        self._inner.focus_set()

    def _on_shift_arrow(self, event: tk.Event) -> str:
        if self._edit_entry is not None:
            pos = self._edit_rc
            self._end_edit(commit=True)
            if pos:
                self._anchor_rc = pos
                self._focus_rc = pos
        else:
            self._end_edit(commit=True)
        if self._anchor_rc is None:
            if self._focus_rc is not None:
                self._anchor_rc = self._focus_rc
            elif self._ordered_keys():
                self._anchor_rc = self._focus_rc = self._ordered_keys()[0]
            else:
                return "break"
        if self._focus_rc is None:
            self._focus_rc = self._anchor_rc
        fr, fc = self._focus_rc
        sym = event.keysym
        if sym == "Up":
            self._focus_rc = (max(0, fr - 1), fc)
        elif sym == "Down":
            self._focus_rc = (min(max(0, len(self._size1_rows) - 1), fr + 1), fc)
        elif sym == "Left":
            self._focus_rc = (fr, max(0, fc - 1))
        elif sym == "Right":
            self._focus_rc = (fr, min(max(0, len(self._size2_cols) - 1), fc + 1))
        self._clamp_anchor_focus()
        self._selected_cells = set(self._rect_cells_corners(self._anchor_rc, self._focus_rc))
        self._prune_selected_to_labels()
        self._refresh_all_cell_styles()
        self._inner.focus_set()
        return "break"

    def _move_same_col(self, ri: int, ci: int, delta: int) -> tuple[int, int] | None:
        if delta > 0:
            seq = range(ri + 1, len(self._size1_rows))
        else:
            seq = range(ri - 1, -1, -1)
        for r in seq:
            if (r, ci) in self._labels:
                return r, ci
        return None

    def _move_same_row(self, ri: int, ci: int, delta: int) -> tuple[int, int] | None:
        if delta > 0:
            seq = range(ci + 1, len(self._size2_cols))
        else:
            seq = range(ci - 1, -1, -1)
        for c in seq:
            if (ri, c) in self._labels:
                return ri, c
        return None

    def _f2_edit(self) -> str:
        self._clamp_anchor_focus()
        if self._focus_rc and self._focus_rc in self._labels:
            self._begin_edit(self._focus_rc[0], self._focus_rc[1], None)
        return "break"

    def _on_browse_keypress(self, event: tk.Event) -> str | None:
        if self._edit_entry is not None:
            return None
        if event.state & 0x4:
            return None
        ch = event.char
        if ch and len(ch) == 1 and ch.isprintable() and not ch.isspace():
            self._clamp_anchor_focus()
            if self._focus_rc and self._focus_rc in self._labels:
                self._begin_edit(self._focus_rc[0], self._focus_rc[1], ch.upper())
            return "break"
        return None

    def _reset_template(self) -> None:
        if not self._askyesno_modal(
            "Reset",
            "Clear all Item_Type values in the matrix?\n"
            "Size1 / Size2 axis enable flags are not changed.",
        ):
            return
        self._values.clear()
        self._rebuild_grid()

    def _rows_from_matrix(self) -> list[SizeTableRow]:
        out: list[SizeTableRow] = []
        for ri, s1 in enumerate(self._size1_rows):
            for ci, s2 in enumerate(self._size2_cols):
                if not cell_allowed(s1, s2, self._pair_kind):
                    continue
                if not self._axis_enabled_size1.get(s1, True):
                    continue
                if not self._axis_enabled_size2.get(s2, True):
                    continue
                it = self._values.get((s1, s2), "").strip().upper()
                if not it:
                    continue
                out.append(SizeTableRow(s1, s2, it, ""))
        return sorted(out, key=lambda r: (size_number(r.size1), size_number(r.size2)))

    def _on_ok(self) -> None:
        self._end_edit(commit=True)
        self._result = NamedSizeTable(self._table_code, self._rows_from_matrix())
        self.destroy()

    def _on_cancel(self) -> None:
        self._end_edit(commit=False)
        self._result = None
        self.destroy()


def run_size_matrix_editor(
    parent: tk.Widget,
    title: str,
    table: NamedSizeTable,
    pair_kind: Literal["reducing", "branch"],
    nominal_mode: str | None = None,
) -> NamedSizeTable | None:
    dlg = MatrixTableDialog(parent, title, table, pair_kind, nominal_mode)
    parent.winfo_toplevel().wait_window(dlg)
    return dlg._result
