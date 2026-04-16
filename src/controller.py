from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import tkinter as tk
from tkinter import messagebox

import gui
import config
from class_template_wizard import run_class_level_wizard
from template_generator import (
    DEFAULT_TEMPLATE_FILENAME,
    generate_class_define_template,
    load_class_level_bundle_from_template,
)
import file_handler
import pms_generator
from project_constraints import validate_project_constraints
from project_config_service import load_current_settings, save_and_reload
from project_settings_dialog import open_project_settings


def create_controller(root: tk.Tk) -> None:
    """
    controller.py는 흐름 제어만 담당합니다.
    - gui.py: 화면(UI) 구성
    - controller.py: 버튼 클릭 시 처리 흐름
    - 실제 비즈니스 로직 호출은 필요해질 때 각 버튼 핸들러에서 연결
    """

    state: dict[str, Optional[str]] = {
        "selected_input_path": None,
    }

    status_setter: Callable[[str], None] = lambda _msg: None

    def _check_project_constraints() -> bool:
        """프로젝트 설정 검증. 통과 시 True, 실패 시 status 표시 후 False."""
        errors = validate_project_constraints(config.config_manager.merged())
        if errors:
            preview = "; ".join(errors[:3])
            if len(errors) > 3:
                preview += f" … 외 {len(errors) - 3}건"
            status_setter(f"프로젝트 설정 검증 실패: {preview}")
            return False
        return True

    def on_project_settings() -> None:
        current = load_current_settings()

        def handle_save(candidate):
            warnings = save_and_reload(candidate)
            if warnings:
                return warnings
            status_setter("프로젝트 설정 저장 완료 (다음 작업부터 반영)")
            return []

        open_project_settings(root, current, handle_save)

    def on_template_create() -> None:
        if not _check_project_constraints():
            return

        save_dir = file_handler.select_save_folder(root)
        if not save_dir:
            status_setter("대기중")
            return

        status_setter("클래스 수준 입력…")
        bundle = run_class_level_wizard(root)
        if bundle is None:
            status_setter("대기중")
            return

        status_setter("템플릿 생성 중...")
        try:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = Path(save_dir) / "template" / stamp
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / DEFAULT_TEMPLATE_FILENAME
            generate_class_define_template(output_path=out_path, class_level=bundle)
            status_setter(f"템플릿 생성 완료: {out_path}")
        except Exception as exc:
            status_setter(f"템플릿 생성 실패: {exc}")

    def on_template_edit() -> None:
        if not _check_project_constraints():
            return

        src_path = file_handler.select_excel_file(root)
        if not src_path:
            status_setter("대기중")
            return

        status_setter("기존 템플릿 읽는 중...")
        try:
            seed_bundle = load_class_level_bundle_from_template(src_path)
        except Exception as exc:
            messagebox.showerror("템플릿 수정", f"템플릿 읽기 실패:\n{exc}", parent=root)
            status_setter(f"템플릿 읽기 실패: {exc}")
            return

        save_dir = file_handler.select_save_folder(root)
        if not save_dir:
            status_setter("대기중")
            return

        status_setter("클래스 수준 입력…")
        bundle = run_class_level_wizard(root, initial_bundle=seed_bundle)
        if bundle is None:
            status_setter("대기중")
            return

        status_setter("수정 템플릿 저장 중...")
        try:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = Path(save_dir) / "template" / stamp
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / DEFAULT_TEMPLATE_FILENAME
            generate_class_define_template(output_path=out_path, class_level=bundle)
            status_setter(f"템플릿 수정 저장 완료: {out_path}")
        except Exception as exc:
            status_setter(f"템플릿 저장 실패: {exc}")

    def on_file_load() -> None:
        status_setter("파일 선택 중...")
        selected = file_handler.select_excel_file(root)
        if not selected:
            status_setter("대기중")
            return
        state["selected_input_path"] = selected
        status_setter(f"파일 불러옴: {selected}")

    def on_pms_generate() -> None:
        input_path = state["selected_input_path"]
        if not input_path:
            status_setter("먼저 파일 불러오기를 해주세요.")
            return

        save_root = file_handler.select_pms_output_folder(root)
        if not save_root:
            status_setter("대기중")
            return

        # 선택 폴더 / output / YYYYMMDD_HHMMSS / 자재 클래스 xlsx
        out_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path(save_root) / "output" / out_stamp
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / pms_generator.OUTPUT_FILENAME

        if not _check_project_constraints():
            return

        status_setter("Piping Material Class Data 생성 중...")
        try:
            out_path = pms_generator.generate_piping_material_class_data(
                input_path,
                output_path=output_path,
            )
            status_setter(f"생성 완료: {out_path}")
        except Exception as exc:
            status_setter(f"생성 실패: {exc}")

    status_setter = gui.build_gui(
        root=root,
        on_project_settings=on_project_settings,
        on_template_create=on_template_create,
        on_template_edit=on_template_edit,
        on_file_load=on_file_load,
        on_pms_generate=on_pms_generate,
    )

    status_setter("대기중")
