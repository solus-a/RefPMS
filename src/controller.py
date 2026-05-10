from __future__ import annotations

from typing import Callable

import tkinter as tk
from tkinter import messagebox

import gui
import file_handler
from class_template_wizard import run_class_level_wizard
from project_codec import ProjectFileError, load_project


def create_controller(root: tk.Tk) -> None:
    """controller.py는 흐름 제어만 담당합니다.

    메인창은 New Project / Open Project 두 진입점만 가지며, 그 후의 작업
    (Save / Export xlsx / Close)은 wizard 내부에서 모두 처리됩니다.
    """

    status_setter: Callable[[str], None] = lambda _msg: None

    def on_new_project() -> None:
        status_setter("새 프로젝트 작업 중...")
        run_class_level_wizard(root)
        status_setter("대기중")

    def on_open_project() -> None:
        path = file_handler.select_project_open_path(root)
        if not path:
            status_setter("대기중")
            return
        status_setter("프로젝트 여는 중...")
        try:
            bundle = load_project(path)
        except ProjectFileError as exc:
            messagebox.showerror("Open Project", f"프로젝트 열기 실패:\n{exc}", parent=root)
            status_setter(f"열기 실패: {exc}")
            return
        run_class_level_wizard(root, initial_bundle=bundle, initial_project_path=path)
        status_setter("대기중")

    status_setter = gui.build_gui(
        root=root,
        on_new_project=on_new_project,
        on_open_project=on_open_project,
    )

    status_setter("대기중")
