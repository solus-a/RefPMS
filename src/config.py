"""프로그램 루트 및 내부 data 경로 (작업 폴더와 분리)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def program_root() -> Path:
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    return program_root() / "data"


def item_code_db_path() -> Path:
    return data_dir() / "Item_Code_DB.xlsx"


def class_material_mapping_path() -> Path:
    """Class_Base_Material → 허용 ASTM/규격 토큰(JSON). 사용자 프로젝트에 맞게 편집."""
    return data_dir() / "class_material_mapping.json"


def project_config_path() -> Path:
    return program_root() / "project_config.json"


class ProjectConfig:
    """프로젝트별 설정을 관리하는 싱글톤 클래스입니다."""
    _instance = None
    _config: dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProjectConfig, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        path = project_config_path()
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        else:
            # 기본값 (파일이 없을 경우 대비)
            self._config = {
                "project_info": {"unit_system": "Inch"},
                "nps_master": {"nps_list": []},
                "output_settings": {
                    "filename": "Piping_Material_Class_Data.xlsx",
                    "sheet_name": "Piping_Material_Class_Data",
                    "columns": [],
                    "item_order": []
                }
            }

    def get(self, key_path: str, default: Any = None) -> Any:
        """점 표기법(예: 'nps_master.nps_list')으로 설정값을 가져옵니다."""
        keys = key_path.split(".")
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value


# 전역 설정 인스턴스
config_manager = ProjectConfig()
