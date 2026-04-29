from __future__ import annotations

import tkinter as tk


class MatrixEditOpsMixin:
    def _begin_edit(self, ri: int, ci: int, first_char: str | None) -> None:
        self._end_edit(commit=True)
        lb = self._labels.get((ri, ci))
        if not lb:
            return
        s1, s2 = self._key(ri, ci)
        cur = self._values.get((s1, s2), "")
        self._edit_rc = (ri, ci)
        ent = tk.Entry(lb.master, relief="solid", bd=1)
        ent.place(in_=lb, x=0, y=0, relwidth=1, relheight=1)
        if first_char is None:
            ent.insert(0, cur)
        else:
            ent.insert(0, first_char)
        ent.focus_set()
        ent.icursor(tk.END)
        if first_char is None:
            ent.selection_range(0, tk.END)

        def commit(_e=None) -> str:
            self._end_edit(commit=True)
            return "break"

        def cancel(_e=None) -> str:
            self._end_edit(commit=False)
            return "break"

        ent.bind("<Return>", commit)
        ent.bind("<Escape>", cancel)
        ent.bind("<FocusOut>", lambda e: self.after(1, self._focusout_edit))
        ent.bind("<Control-Return>", lambda e: self._ctrl_enter_fill())

        def _ec(_e=None) -> str:
            self._copy_selection()
            return "break"

        def _ev(_e=None) -> str:
            self._paste_at_focus()
            return "break"

        ent.bind("<Control-c>", _ec)
        ent.bind("<Control-v>", _ev)

        def _entry_upper(_e=None) -> None:
            cur = ent.get()
            up = cur.upper()
            if cur == up:
                return
            try:
                ip = int(ent.index(tk.INSERT))
            except (tk.TclError, ValueError, TypeError):
                ip = len(up)
            ent.delete(0, tk.END)
            ent.insert(0, up)
            try:
                ent.icursor(min(ip, len(up)))
            except tk.TclError:
                ent.icursor(tk.END)

        ent.bind("<KeyRelease>", _entry_upper)
        for seq in ("<Up>", "<Down>", "<Left>", "<Right>"):
            ent.bind(seq, self._on_arrow)
        self._edit_entry = ent

    def _focusout_edit(self) -> None:
        if self._edit_entry is None:
            return
        fw = self.focus_get()
        if fw is self._edit_entry:
            return
        self._end_edit(commit=True)

    def _end_edit(self, commit: bool) -> None:
        ent = self._edit_entry
        rc = self._edit_rc
        self._edit_entry = None
        self._edit_rc = None
        if ent is None or rc is None:
            if ent:
                ent.place_forget()
                ent.destroy()
            return
        ri, ci = rc
        lb = self._labels.get((ri, ci))
        if commit:
            val = ent.get().strip().upper()
            s1, s2 = self._key(ri, ci)
            if self._value_allowed_for_cell(s1, s2, val):
                self._values[(s1, s2)] = val
                if lb:
                    lb.config(text=val)
            elif lb:
                lb.config(text=self._values.get((s1, s2), ""))
        ent.place_forget()
        ent.destroy()
        self._inner.focus_set()
        self._refresh_all_cell_styles()

    def _active_cell_value(self) -> str:
        if self._edit_entry is not None:
            return self._edit_entry.get().strip().upper()
        if self._focus_rc and self._focus_rc in self._labels:
            ri, ci = self._focus_rc
            s1, s2 = self._key(ri, ci)
            return self._values.get((s1, s2), "").strip().upper()
        return ""

    def _ctrl_enter_fill(self) -> str:
        self._end_edit(commit=True)
        self._clamp_anchor_focus()
        self._prune_selected_to_labels()
        targets = [c for c in self._selected_cells if c in self._labels]
        if not targets:
            return "break"
        val = self._active_cell_value()
        for ri, ci in targets:
            s1, s2 = self._key(ri, ci)
            if not self._value_allowed_for_cell(s1, s2, val):
                continue
            self._values[(s1, s2)] = val
            self._labels[(ri, ci)].config(text=val)
        self._refresh_all_cell_styles()
        return "break"

    def _copy_selection(self) -> None:
        cells = self._selected_cells & self._labels.keys()
        if not cells:
            if self._focus_rc and self._focus_rc in self._labels:
                ri, ci = self._focus_rc
                self.clipboard_clear()
                self.clipboard_append(self._values.get(self._key(ri, ci), ""))
            return
        if len(cells) == 1:
            ri, ci = next(iter(cells))
            self.clipboard_clear()
            self.clipboard_append(self._values.get(self._key(ri, ci), ""))
            return
        r0 = min(r for r, _ in cells)
        r1 = max(r for r, _ in cells)
        c0 = min(c for _, c in cells)
        c1 = max(c for _, c in cells)
        lines = []
        for ri in range(r0, r1 + 1):
            row = []
            for ci in range(c0, c1 + 1):
                if (ri, ci) in self._labels:
                    row.append(
                        self._values.get(self._key(ri, ci), "")
                        if (ri, ci) in cells
                        else ""
                    )
                else:
                    row.append("")
            lines.append("\t".join(row))
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))

    def _paste_at_focus(self) -> None:
        if self._focus_rc is None:
            return
        try:
            txt = self.clipboard_get()
        except tk.TclError:
            return
        ri0, ci0 = self._focus_rc
        lines = txt.replace("\r\n", "\n").replace("\r", "\n").strip("\n").split("\n")
        for di, line in enumerate(lines):
            parts = line.split("\t")
            for dj, part in enumerate(parts):
                ri, ci = ri0 + di, ci0 + dj
                if (ri, ci) in self._labels:
                    s1, s2 = self._key(ri, ci)
                    v = part.strip().upper()
                    if not self._value_allowed_for_cell(s1, s2, v):
                        continue
                    self._values[(s1, s2)] = v
                    self._labels[(ri, ci)].config(text=v)
        self._refresh_all_cell_styles()
