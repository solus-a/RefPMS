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


_last_project_dir: Optional[str] = None


def _remember_project_dir(path: str) -> None:
    global _last_project_dir
    parent = Path(path).resolve().parent
    if parent.is_dir():
        _last_project_dir = str(parent)


def select_project_save_path(
    root: tk.Tk, default_name: str = "Project"
) -> Optional[str]:
    """프로젝트 JSON 저장 경로를 사용자에게 묻는다. 마지막 폴더를 기본값으로."""
    _refresh_root(root)
    file_path = filedialog.asksaveasfilename(
        parent=root,
        title="프로젝트 저장",
        defaultextension=".json",
        initialfile=f"{default_name}.json",
        initialdir=_last_project_dir,
        filetypes=[("RefPMS Project (JSON)", "*.json"), ("All files", "*.*")],
    )
    if not file_path:
        return None
    p = Path(file_path).resolve()
    _remember_project_dir(str(p))
    return str(p)


def select_project_open_path(root: tk.Tk) -> Optional[str]:
    """프로젝트 JSON 열기 경로를 사용자에게 묻는다. 마지막 폴더를 기본값으로."""
    _refresh_root(root)
    file_path = filedialog.askopenfilename(
        parent=root,
        title="프로젝트 열기",
        initialdir=_last_project_dir,
        filetypes=[("RefPMS Project (JSON)", "*.json"), ("All files", "*.*")],
    )
    if not file_path:
        return None
    p = Path(file_path)
    if not p.exists():
        return None
    resolved = p.resolve()
    _remember_project_dir(str(resolved))
    return str(resolved)
