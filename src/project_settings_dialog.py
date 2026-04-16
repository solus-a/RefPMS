"""프로젝트 설정 편집 다이얼로그 (tkinter UI only)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from project_config_service import (
    BOLT_THREAD_OPTIONS,
    DESIGN_CODE_OPTIONS,
    NOMINAL_SIZE_OPTIONS,
    PIPE_THREAD_OPTIONS,
    UNIT_SYSTEM_OPTIONS,
    ProjectSettings,
    _design_unit_options,
)

_LABEL_WIDTH = 22
_COMBO_WIDTH = 28


class ProjectSettingsDialog(tk.Toplevel):
    """단순 폼: 드롭다운만으로 프로젝트 설정을 편집합니다."""

    def __init__(
        self,
        parent: tk.Misc,
        current: ProjectSettings,
        on_save: Callable[[ProjectSettings], list[str]],
    ) -> None:
        super().__init__(parent)
        self.title("프로젝트 설정")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self._on_save = on_save

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        row = 0

        # --- Unit system ---
        row = self._add_combo(
            frame, row, "단위 체계", UNIT_SYSTEM_OPTIONS, current.unit_system, "_unit_system",
        )

        # --- Temperature / Pressure (dependent on unit system) ---
        t_opts, p_opts = _design_unit_options(current.unit_system)
        row = self._add_combo(
            frame, row, "온도 단위", t_opts, current.temperature_unit, "_temperature",
        )
        row = self._add_combo(
            frame, row, "압력 단위", p_opts, current.pressure_unit, "_pressure",
        )

        # --- Nominal size ---
        row = self._add_combo(
            frame, row, "공칭 사이즈 표기", NOMINAL_SIZE_OPTIONS, current.nominal_size, "_nominal_size",
        )

        # --- Pipe thread ---
        row = self._add_combo(
            frame, row, "파이프 나사 규격", PIPE_THREAD_OPTIONS, current.pipe_thread, "_pipe_thread",
        )

        # --- Bolt thread ---
        row = self._add_combo(
            frame, row, "볼트 나사 규격", BOLT_THREAD_OPTIONS, current.bolt_thread, "_bolt_thread",
        )

        # --- Design code ---
        row = self._add_combo(
            frame, row, "설계 코드", DESIGN_CODE_OPTIONS, current.design_code, "_design_code",
        )

        # --- Buttons ---
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=(16, 0))
        ttk.Button(btn_frame, text="저장", command=self._do_save).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="취소", command=self.destroy).pack(side="left", padx=8)

        # Bind unit_system change → update temperature/pressure options
        self._unit_system_combo.bind("<<ComboboxSelected>>", self._on_unit_system_changed)

    # ----- helpers -----

    def _add_combo(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        values: tuple[str, ...],
        current_value: str,
        attr_name: str,
    ) -> int:
        ttk.Label(parent, text=label, width=_LABEL_WIDTH, anchor="w").grid(
            row=row, column=0, sticky="w", pady=4,
        )
        cb = ttk.Combobox(parent, width=_COMBO_WIDTH, state="readonly", values=list(values))
        cb.set(current_value if current_value in values else (values[0] if values else ""))
        cb.grid(row=row, column=1, sticky="ew", pady=4, padx=(8, 0))
        setattr(self, f"{attr_name}_combo", cb)
        return row + 1

    def _on_unit_system_changed(self, _event: tk.Event | None = None) -> None:
        selected_system = self._unit_system_combo.get()
        t_opts, p_opts = _design_unit_options(selected_system)

        self._temperature_combo["values"] = list(t_opts)
        self._temperature_combo.set(t_opts[0] if t_opts else "")

        self._pressure_combo["values"] = list(p_opts)
        self._pressure_combo.set(p_opts[0] if p_opts else "")

    def _do_save(self) -> None:
        candidate = ProjectSettings(
            unit_system=self._unit_system_combo.get(),
            temperature_unit=self._temperature_combo.get(),
            pressure_unit=self._pressure_combo.get(),
            nominal_size=self._nominal_size_combo.get(),
            pipe_thread=self._pipe_thread_combo.get(),
            bolt_thread=self._bolt_thread_combo.get(),
            design_code=self._design_code_combo.get(),
        )
        errors = self._on_save(candidate)
        if errors:
            from tkinter import messagebox
            messagebox.showerror("설정 저장 실패", "\n".join(errors), parent=self)
            return
        self.destroy()


def open_project_settings(
    parent: tk.Misc,
    current: ProjectSettings,
    on_save: Callable[[ProjectSettings], list[str]],
) -> None:
    """설정 다이얼로그를 열고, 사용자가 닫을 때까지 블록합니다."""
    dlg = ProjectSettingsDialog(parent, current, on_save)
    parent.wait_window(dlg)
