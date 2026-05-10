from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


OnNewProject = Callable[[], None]
OnOpenProject = Callable[[], None]


def build_gui(
    root: tk.Tk,
    on_new_project: OnNewProject,
    on_open_project: OnOpenProject,
) -> Callable[[str], None]:
    """메인창은 New / Open Project 두 진입점만 노출합니다.

    Save / Export / Close 등 프로젝트 작업 자체는 wizard 내부에서 처리합니다.
    """
    root.title("Piping Material Class")
    root.geometry("520x160")

    main_frame = ttk.Frame(root, padding=12)
    main_frame.grid(row=0, column=0, sticky="nsew")

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    buttons_frame = ttk.Frame(main_frame)
    buttons_frame.grid(row=0, column=0, sticky="ew")

    btn_new = ttk.Button(buttons_frame, text="New Project", command=on_new_project)
    btn_open = ttk.Button(buttons_frame, text="Open Project", command=on_open_project)

    btn_new.grid(row=0, column=0, padx=(0, 8), pady=8, sticky="ew")
    btn_open.grid(row=0, column=1, padx=(0, 0), pady=8, sticky="ew")

    for col in range(2):
        buttons_frame.columnconfigure(col, weight=1)

    status_var = tk.StringVar(value="대기중")
    status_label = ttk.Label(main_frame, textvariable=status_var, anchor="w")
    status_label.grid(row=1, column=0, sticky="ew")

    def set_status(message: str) -> None:
        status_var.set(message)
        root.update_idletasks()

    return set_status
