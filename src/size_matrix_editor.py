"""Matrix editor for reducing/branch size tables (Excel-like: browse + F2/edit + Ctrl+click).

Per-table size axes are derived from a single Size_From / Size_To range intersected with the
template's Global Size Selection. Reducing tables: cells with Size2 >= Size1 are disabled
(reducing/swage requires Size2 < Size1). Branch tables: cells with Size2 > Size1 are disabled.
"""

from __future__ import annotations

from tkinter import messagebox
from typing import Literal

import tkinter as tk
from tkinter import ttk

import config
from class_level_model import NamedSizeTable, SizeSelection, SizeTableRow, _resolve_active_sizes
from size_matrix_common import (
    BRANCH_ITEM_TYPES_OK,
    REDUCING_ITEM_TYPES_OK,
    normalize_nominal_mode,
    size_number,
)
from size_matrix_edit_ops import MatrixEditOpsMixin


def _selected_size_pool(selection: SizeSelection, mode: str) -> list[str]:
    raw = selection.for_mode(mode)
    if not raw:
        return list(config.catalog_sizes_all(mode))
    catalog = list(config.catalog_sizes_all(mode))
    raw_set = set(raw)
    return [s for s in catalog if s in raw_set]


class MatrixTableDialog(MatrixEditOpsMixin, tk.Toplevel):
    """
    Rows = Size1, columns = Size2; titles on dedicated header row/column.
    Selection is clamped to editable (label) cells only.
    Axis sizes are derived from (table.size_from..table.size_to) ∩ Global Size Selection.
    """

    GRID_DATA_ROW0 = 2

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        table: NamedSizeTable,
        pair_kind: Literal["reducing", "branch"],
        nominal_mode: str | None = None,
        size_selection: SizeSelection | None = None,
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
        self._size_selection = size_selection or SizeSelection()
        self._size_pool = _selected_size_pool(self._size_selection, self._nominal_mode)
        self._size_from = (table.size_from or "").strip()
        self._size_to = (table.size_to or "").strip()
        self._axis_sizes = self._compute_axis_sizes()

        self._values: dict[tuple[str, str], str] = {}
        for r in table.rows:
            k = (r.size1.strip(), r.size2.strip())
            if r.item_type.strip():
                self._values[k] = r.item_type.strip().upper()

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

        self.geometry("960x680")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        ttk.Label(top, text=f"Table: {self._table_code}", font=("", 11, "bold")).pack(
            side="left", padx=(0, 12)
        )
        ttk.Label(top, text=f"Mode: {self._nominal_mode}").pack(side="left", padx=(0, 12))

        range_box = ttk.Frame(self)
        range_box.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))
        ttk.Label(range_box, text="Size_From").pack(side="left", padx=(0, 4))
        self._cb_from = ttk.Combobox(
            range_box, width=10, state="readonly", values=["", *self._size_pool]
        )
        self._cb_from.pack(side="left", padx=(0, 12))
        ttk.Label(range_box, text="Size_To").pack(side="left", padx=(0, 4))
        self._cb_to = ttk.Combobox(
            range_box, width=10, state="readonly", values=["", *self._size_pool]
        )
        self._cb_to.pack(side="left", padx=(0, 12))
        ttk.Button(range_box, text="Apply", command=self._on_apply_range).pack(side="left")

        if self._size_from and self._size_from in self._size_pool:
            self._cb_from.set(self._size_from)
        if self._size_to and self._size_to in self._size_pool:
            self._cb_to.set(self._size_to)

        tb = ttk.Frame(self)
        tb.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
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
        ax.grid(row=3, column=0, sticky="ew", padx=4, pady=2)
        ttk.Button(ax, text="Reset", command=self._reset_template).pack(side="left", padx=8)

        bf = ttk.Frame(self)
        bf.grid(row=4, column=0, pady=8)
        ttk.Button(bf, text="OK", command=self._on_ok).pack(side="left", padx=6)
        ttk.Button(bf, text="Cancel", command=self._on_cancel).pack(side="left", padx=6)

        self.protocol("WM_DELETE_WINDOW", lambda: self._on_cancel())
        self.after(80, lambda: self._inner.focus_set())

    def _compute_axis_sizes(self) -> list[str]:
        """현재 Size_From / Size_To 와 Global Size Selection 의 교집합 (카탈로그 순서).

        Size_From / Size_To 중 하나라도 비어 있으면 빈 축으로 간주 — Apply range 전에는 매트릭스가 렌더되지 않음.
        """
        if not self._size_from or not self._size_to:
            return []
        return _resolve_active_sizes(
            self._size_selection, self._nominal_mode, self._size_from, self._size_to
        )

    def _on_apply_range(self) -> None:
        sf = (self._cb_from.get() or "").strip()
        st = (self._cb_to.get() or "").strip()
        if sf and st:
            try:
                if float(st) < float(sf):
                    messagebox.showerror(
                        "Invalid range",
                        "Size_To must be greater than or equal to Size_From.",
                        parent=self,
                    )
                    return
            except ValueError:
                pass
        self._size_from = sf
        self._size_to = st
        self._axis_sizes = self._compute_axis_sizes()
        self._rebuild_grid()

    def _row_axis_title(self) -> str:
        return "Header size" if self._pair_kind == "branch" else "Main Size"

    def _col_axis_title(self) -> str:
        return "Branch Size" if self._pair_kind == "branch" else "Reducing Size"

    def _cell_allowed(self, s1: str, s2: str) -> bool:
        try:
            n1 = size_number(s1)
            n2 = size_number(s2)
        except (TypeError, ValueError):
            return False
        if self._pair_kind == "reducing":
            return n2 < n1
        return n2 <= n1

    def _item_ok(self, raw: str) -> bool:
        v = raw.strip().upper()
        if not v:
            return True
        if self._pair_kind == "branch":
            return v in BRANCH_ITEM_TYPES_OK
        return v in REDUCING_ITEM_TYPES_OK

    def _value_allowed_for_cell(self, s1: str, s2: str, raw: str) -> bool:
        """셀 (s1, s2) 에 raw 값을 저장할 수 있는지.

        Branch:
          - 대각셀 (Size1 == Size2): 'T' (Equal Tee) 만 허용
          - 비대각셀 (Size1 != Size2): 'T' 는 불가 — 'RT' / 'TH' 만 허용
        Reducing: 타입 집합 검사만.
        """
        v = raw.strip().upper()
        if not v:
            return True
        if not self._item_ok(v):
            return False
        if self._pair_kind == "branch":
            on_diagonal = s1.strip() == s2.strip()
            if on_diagonal:
                return v == "T"
            return v != "T"
        return True

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
        ok = self._value_allowed_for_cell(s1, s2, val)
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
        return self._axis_sizes[ri]

    def _size2_at(self, ci: int) -> str:
        return self._axis_sizes[ci]

    def _key(self, ri: int, ci: int) -> tuple[str, str]:
        return (self._size1_at(ri), self._size2_at(ci))

    @property
    def _size1_rows(self) -> list[str]:
        return self._axis_sizes

    @property
    def _size2_cols(self) -> list[str]:
        return self._axis_sizes

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
        sizes = self._axis_sizes
        n = len(sizes)
        gr0 = MatrixTableDialog.GRID_DATA_ROW0

        if n == 0:
            tk.Label(
                inner,
                text="Please select Size Range.",
                fg="#666666",
                padx=12,
                pady=12,
            ).grid(row=0, column=0)
            return

        tk.Label(inner, text="", width=11, relief="ridge").grid(row=0, column=0, sticky="nsew")
        col_span = max(1, n)
        tk.Label(
            inner,
            text=self._col_axis_title(),
            relief="ridge",
            anchor="center",
        ).grid(row=0, column=1, columnspan=col_span, sticky="nsew")

        tk.Label(inner, text=self._row_axis_title(), relief="ridge", anchor="center").grid(
            row=1, column=0, sticky="nsew"
        )
        for ci, s2 in enumerate(sizes):
            tk.Label(inner, text=s2, width=6, relief="ridge").grid(row=1, column=ci + 1, sticky="nsew")

        for ri, s1 in enumerate(sizes):
            tk.Label(inner, text=s1, width=13, relief="ridge").grid(
                row=gr0 + ri, column=0, sticky="nsew"
            )
            for ci, s2 in enumerate(sizes):
                allowed = self._cell_allowed(s1, s2)
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
        n = len(self._axis_sizes)
        if sym == "Up":
            self._focus_rc = (max(0, fr - 1), fc)
        elif sym == "Down":
            self._focus_rc = (min(max(0, n - 1), fr + 1), fc)
        elif sym == "Left":
            self._focus_rc = (fr, max(0, fc - 1))
        elif sym == "Right":
            self._focus_rc = (fr, min(max(0, n - 1), fc + 1))
        self._clamp_anchor_focus()
        self._selected_cells = set(self._rect_cells_corners(self._anchor_rc, self._focus_rc))
        self._prune_selected_to_labels()
        self._refresh_all_cell_styles()
        self._inner.focus_set()
        return "break"

    def _move_same_col(self, ri: int, ci: int, delta: int) -> tuple[int, int] | None:
        n = len(self._axis_sizes)
        if delta > 0:
            seq = range(ri + 1, n)
        else:
            seq = range(ri - 1, -1, -1)
        for r in seq:
            if (r, ci) in self._labels:
                return r, ci
        return None

    def _move_same_row(self, ri: int, ci: int, delta: int) -> tuple[int, int] | None:
        n = len(self._axis_sizes)
        if delta > 0:
            seq = range(ci + 1, n)
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
            "Clear all Item_Type values in the matrix?",
        ):
            return
        self._values.clear()
        self._rebuild_grid()

    def _rows_from_matrix(self) -> list[SizeTableRow]:
        out: list[SizeTableRow] = []
        sizes = self._axis_sizes
        for s1 in sizes:
            for s2 in sizes:
                if not self._cell_allowed(s1, s2):
                    continue
                it = self._values.get((s1, s2), "").strip().upper()
                if not it:
                    continue
                out.append(SizeTableRow(s1, s2, it, ""))
        return sorted(out, key=lambda r: (size_number(r.size1), size_number(r.size2)))

    def _on_ok(self) -> None:
        self._end_edit(commit=True)
        sf = (self._cb_from.get() or "").strip()
        st = (self._cb_to.get() or "").strip()
        if sf and st:
            try:
                if float(st) < float(sf):
                    messagebox.showerror(
                        "Invalid range",
                        "Size_To must be greater than or equal to Size_From.",
                        parent=self,
                    )
                    return
            except ValueError:
                pass
        self._size_from = sf
        self._size_to = st
        self._result = NamedSizeTable(
            table_code=self._table_code,
            rows=self._rows_from_matrix(),
            nominal_mode=self._nominal_mode,
            size_from=self._size_from,
            size_to=self._size_to,
        )
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
    size_selection: SizeSelection | None = None,
) -> NamedSizeTable | None:
    dlg = MatrixTableDialog(parent, title, table, pair_kind, nominal_mode, size_selection)
    parent.winfo_toplevel().wait_window(dlg)
    return dlg._result
