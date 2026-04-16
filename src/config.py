"""프로그램 루트 및 내부 data 경로 (작업 폴더와 분리)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from project_constraints import validate_project_constraints


def program_root() -> Path:
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    return program_root() / "data"


def item_code_db_path() -> Path:
    return data_dir() / "Item_Code_DB.xlsx"


def config_root() -> Path:
    """프로그램 루트의 `config/` (project·generator 하위)."""
    return program_root() / "config"


def class_material_mapping_path() -> Path:
    """Class_Base_Material 대비 부품 Mat 토큰 허용 목록 — 엔진 검증용 (`data/`). Piping class 정의(Class_Define)와는 별개."""
    return data_dir() / "class_material_mapping.json"


def component_mapping_path() -> Path:
    """부품군별 필수·조건부·배타 속성 규칙(JSON). Phase 3 동적 Validator 입력."""
    return data_dir() / "component_mapping.json"


def project_config_dir() -> Path:
    """프로젝트 단위 설정 JSON (`config/project/`)."""
    return config_root() / "project"


def generator_config_dir() -> Path:
    """Micro DB 생성기 출력·코딩 규칙 (`config/generator/`)."""
    return config_root() / "generator"


def _read_json_dict(path: Path, logger: logging.Logger) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return {}
    if not isinstance(raw, dict):
        logger.warning("Expected JSON object in %s, got %s", path, type(raw).__name__)
        return {}
    return raw


class ProjectConfig:
    """프로젝트(`config/project/`)·생성기(`config/generator/`) 설정을 병합하는 싱글톤."""

    _instance = None
    _config: dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProjectConfig, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        logger = logging.getLogger(__name__)
        proj = project_config_dir()
        gen = generator_config_dir()

        self._config = {
            "units_notation": _read_json_dict(proj / "units_notation.json", logger)
            or {
                "unit_system": {
                    "allowed": ["Metric", "Imperial"],
                    "selected": "Metric",
                    "design_units": {
                        "Metric": {
                            "temperature": {"allowed": ["°C"], "selected": "°C"},
                            "pressure": {
                                "allowed": ["bar", "barg", "kPa", "MPa"],
                                "selected": "bar",
                            },
                        },
                        "Imperial": {
                            "temperature": {"allowed": ["°F"], "selected": "°F"},
                            "pressure": {
                                "allowed": ["psig", "psi", "psia"],
                                "selected": "psig",
                            },
                        },
                    },
                },
                "nominal_size": {"allowed": ["NPS", "DN"], "selected": "DN"},
                "pipe_thread": {"allowed": ["NPT", "PT"], "selected": "NPT"},
                "bolt_thread": {"allowed": ["Metric", "Imperial"], "selected": "Metric"},
            },
            "nps_master": _read_json_dict(proj / "nps_master.json", logger)
            or {"nps_list": [], "dn_list": []},
            "output_settings": _read_json_dict(gen / "output_settings.json", logger)
            or {
                "filename": "Piping_Material_Class_Data.xlsx",
                "sheet_name": "Piping_Material_Class_Data",
                "columns": [],
                "item_order": [],
            },
            "coding_rules": _read_json_dict(gen / "coding_rules.json", logger)
            or {"commodity_code_logic": "fixed_corporate_standard"},
            "validation_policy": _read_json_dict(gen / "validation_policy.json", logger)
            or {
                "corrosion_allowance": {
                    "default_value": "0.0",
                    "empty_value_policy": "warning",
                    "reference_values": {
                        "metric_mm": [
                            "0.0",
                            "0.3",
                            "0.5",
                            "0.8",
                            "1.0",
                            "1.5",
                            "2.0",
                            "3.0",
                            "4.5",
                            "6.0",
                            "9.0",
                            "12.0",
                        ],
                        "imperial_inch": [
                            "0.0",
                            "0.012",
                            "0.020",
                            "0.031",
                            "0.039",
                            "0.050",
                            "0.0625",
                            "0.100",
                            "0.125",
                            "0.188",
                            "0.250",
                            "0.375",
                            "0.500",
                        ],
                    },
                }
            },
            "piping_design_codes": _read_json_dict(
                proj / "piping_design_codes.json", logger
            )
            or {
                "allowed": ["ASME B31.3", "ASME B31.4"],
                "selected": "ASME B31.3",
                "notes": (
                    "Typical B31.3/B31.4 scope assumes ASME B16.11 for socket-welded and screwed "
                    "forged fittings; use Fitting_Group End_Type, not a Dim_Standard column."
                ),
            },
        }
        if "nps_list" not in self._config["nps_master"]:
            self._config["nps_master"]["nps_list"] = []
        if "dn_list" not in self._config["nps_master"]:
            self._config["nps_master"]["dn_list"] = []

        for msg in validate_project_constraints(self._config):
            logger.warning("Project constraints: %s", msg)

    def get(self, key_path: str, default: Any = None) -> Any:
        """점 표기법(예: 'nps_master.nps_list')으로 설정값을 가져옵니다."""
        keys = key_path.split(".")
        value: Any = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def reload(self) -> list[str]:
        """디스크에서 설정을 다시 읽고 제약 검증 경고 목록을 반환합니다."""
        self._load_config()
        return validate_project_constraints(self._config)

    def snapshot(self) -> dict[str, Any]:
        """외부 변이가 불가능한 deep copy를 반환합니다."""
        import copy
        return copy.deepcopy(self._config)

    def merged(self) -> dict[str, Any]:
        """검증·다른 모듈 전달용 얕은 복사."""
        return dict(self._config)


# 전역 설정 인스턴스
config_manager = ProjectConfig()
