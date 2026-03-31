"""프로그램 루트 및 내부 data 경로 (작업 폴더와 분리)."""

from __future__ import annotations

from pathlib import Path


def program_root() -> Path:
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    return program_root() / "data"


def item_code_db_path() -> Path:
    return data_dir() / "Item_Code_DB.xlsx"
