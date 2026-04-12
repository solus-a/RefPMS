from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import tkinter as tk

import gui
import config
from class_template_wizard import run_class_level_wizard
from template_generator import DEFAULT_TEMPLATE_FILENAME, generate_class_define_template
import file_handler
import pms_generator
from project_constraints import validate_project_constraints


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

    def on_template_create() -> None:
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
            # 선택 폴더 / template / YYYYMMDD_HHMMSS / 템플릿.xlsx
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = Path(save_dir) / "template" / stamp
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / DEFAULT_TEMPLATE_FILENAME
            generate_class_define_template(output_path=out_path, class_level=bundle)
            status_setter(f"템플릿 생성 완료: {out_path}")
        except Exception as exc:
            status_setter(f"템플릿 생성 실패: {exc}")

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

        constraint_errors = validate_project_constraints(config.config_manager.merged())
        if constraint_errors:
            preview = "; ".join(constraint_errors[:3])
            if len(constraint_errors) > 3:
                preview += f" … 외 {len(constraint_errors) - 3}건"
            status_setter(f"프로젝트 설정 검증 실패: {preview}")
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
        on_template_create=on_template_create,
        on_file_load=on_file_load,
        on_pms_generate=on_pms_generate,
    )

    status_setter("대기중")
