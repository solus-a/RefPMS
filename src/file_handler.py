from __future__ import annotations

from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import filedialog


def _refresh_root(root: tk.Tk) -> None:
    try:
        root.update_idletasks()
    except Exception:
        pass


def select_excel_file(root: tk.Tk) -> Optional[str]:
    """엑셀 파일만 선택합니다."""
    _refresh_root(root)
    file_path = filedialog.askopenfilename(
        parent=root,
        title="엑셀 파일 선택",
        filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")],
    )
    if not file_path:
        return None
    p = Path(file_path)
    if not p.exists():
        return None
    return str(p.resolve())


def select_folder(root: tk.Tk, title: str) -> Optional[str]:
    """저장/출력용 폴더 선택 (제목만 다르게 쓰면 됨)."""
    _refresh_root(root)
    folder = filedialog.askdirectory(parent=root, title=title)
    if not folder:
        return None
    p = Path(folder)
    if not p.is_dir():
        return None
    return str(p.resolve())


def select_save_folder(root: tk.Tk) -> Optional[str]:
    """템플릿 저장 위치(폴더) 선택."""
    return select_folder(root, title="템플릿 저장 폴더 선택")


def select_pms_output_folder(root: tk.Tk) -> Optional[str]:
    """자재 클래스 데이터 저장 위치(폴더) 선택."""
    return select_folder(root, title="자재 클래스 데이터 저장 폴더 선택")
