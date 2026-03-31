from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


OnTemplateCreate = Callable[[], None]
OnFileLoad = Callable[[], None]
OnPmsGenerate = Callable[[], None]


def build_gui(
    root: tk.Tk,
    on_template_create: OnTemplateCreate,
    on_file_load: OnFileLoad,
    on_pms_generate: OnPmsGenerate,
) -> Callable[[str], None]:
    """
    GUI는 화면 구성과 사용자 입력 이벤트 연결만 담당합니다.
    로직/흐름 제어는 controller.py에서 처리합니다.
    """
    root.title("Piping Material Class")
    root.geometry("520x180")

    main_frame = ttk.Frame(root, padding=12)
    main_frame.grid(row=0, column=0, sticky="nsew")

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    buttons_frame = ttk.Frame(main_frame)
    buttons_frame.grid(row=0, column=0, sticky="ew")

    btn_template = ttk.Button(
        buttons_frame, text="템플릿 생성", command=on_template_create
    )
    btn_load = ttk.Button(buttons_frame, text="파일 불러오기", command=on_file_load)
    btn_generate = ttk.Button(
        buttons_frame, text="자재 클래스 데이터 생성", command=on_pms_generate
    )

    btn_template.grid(row=0, column=0, padx=(0, 8), pady=8, sticky="ew")
    btn_load.grid(row=0, column=1, padx=(0, 8), pady=8, sticky="ew")
    btn_generate.grid(row=0, column=2, padx=(0, 0), pady=8, sticky="ew")

    for col in range(3):
        buttons_frame.columnconfigure(col, weight=1)

    status_var = tk.StringVar(value="대기중")
    status_label = ttk.Label(main_frame, textvariable=status_var, anchor="w")
    status_label.grid(row=1, column=0, sticky="ew")

    def set_status(message: str) -> None:
        status_var.set(message)
        # Ensure UI refresh in case controller updates quickly.
        root.update_idletasks()

    return set_status

