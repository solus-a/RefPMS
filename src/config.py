"""프로그램 루트 및 내부 data 경로 (작업 폴더와 분리)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


def program_root() -> Path:
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    return program_root() / "data"


def item_code_db_path() -> Path:
    return data_dir() / "Item_Code_DB.xlsx"


def field_values_db_path() -> Path:
    """그룹별 컴포넌트 필드 드롭다운 값(JSON). Components 탭 다이얼로그에서 사용."""
    return data_dir() / "field_values.json"


def item_code_db_json_path() -> Path:
    """그룹별 Item Code 레지스트리(JSON). Components 탭 다이얼로그의 Item_Code 드롭다운 소스."""
    return data_dir() / "item_code_db.json"


def config_root() -> Path:
    """프로그램 루트의 `config/` (generator 실행 정책 전용)."""
    return program_root() / "config"


def class_material_mapping_path() -> Path:
    """Class_Base_Material 대비 부품 Mat 토큰 허용 목록 — 엔진 검증용 (`data/`). Piping class 정의(Class_Define)와는 별개."""
    return data_dir() / "class_material_mapping.json"


def component_mapping_path() -> Path:
    """부품군별 필수·조건부·배타 속성 규칙(JSON). Phase 3 동적 Validator 입력."""
    return data_dir() / "component_mapping.json"


def nps_catalog_path() -> Path:
    """표준 공칭 사이즈 카탈로그 (ASME B36.10 NPS, ISO 6708 DN). 프로그램 내장 불변 데이터."""
    return data_dir() / "nps_catalog.json"


def nps_dn_pairing_path() -> Path:
    """NPS↔DN 1:1 표준 매핑 (Global Setting Size Selection 표). 프로그램 내장 불변 데이터."""
    return data_dir() / "nps_dn_pairing.json"


def design_codes_path() -> Path:
    """배관 설계 코드 참조 목록 (Class 계층 선택 대상)."""
    return data_dir() / "design_codes.json"


def nominal_size_systems_path() -> Path:
    """공칭 사이즈 체계 참조 목록 (NPS/DN, Class 계층 선택 대상)."""
    return data_dir() / "nominal_size_systems.json"


def unit_systems_path() -> Path:
    """단위 체계 및 design-unit 옵션 참조 (Class Template 전역)."""
    return data_dir() / "unit_systems.json"


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


class GeneratorConfig:
    """생성기 실행 정책(`config/generator/`) + 내장 카탈로그 병합 싱글톤.

    Class 계층 값 (unit_system, nominal_size_system, design_code, pipe/bolt thread 등) 은
    여기에 보관하지 않는다. 그런 값은 Class_Define 시트 또는 `data/*.json` 참조 데이터에서
    직접 읽어야 한다.
    """

    _instance = None
    _config: dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GeneratorConfig, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        logger = logging.getLogger(__name__)
        gen = generator_config_dir()

        self._config = {
            "nps_catalog": _read_json_dict(nps_catalog_path(), logger)
            or {"version": 0, "nps": [], "dn": []},
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
        }
        if "nps" not in self._config["nps_catalog"]:
            self._config["nps_catalog"]["nps"] = []
        if "dn" not in self._config["nps_catalog"]:
            self._config["nps_catalog"]["dn"] = []

    def get(self, key_path: str, default: Any = None) -> Any:
        """점 표기법(예: 'output_settings.filename')으로 설정값을 가져옵니다."""
        keys = key_path.split(".")
        value: Any = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def reload(self) -> None:
        """디스크에서 설정을 다시 읽는다."""
        self._load_config()

    def snapshot(self) -> dict[str, Any]:
        """외부 변이가 불가능한 deep copy를 반환합니다."""
        import copy
        return copy.deepcopy(self._config)


# 전역 설정 인스턴스 (기존 이름 유지 — Class 레벨 이외 호출부는 동일 API 사용)
config_manager = GeneratorConfig()


# ---------------------------------------------------------------------------
# NPS/DN catalog helpers (program-internal, immutable)
# ---------------------------------------------------------------------------

def _catalog_entries(kind: str) -> list[dict[str, Any]]:
    raw = config_manager.get(f"nps_catalog.{kind}", []) or []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict) and item.get("size") is not None:
            out.append(item)
    return out


def _catalog_sizes(kind: str, preferred_only: bool) -> list[str]:
    out: list[str] = []
    for item in _catalog_entries(kind):
        size_text = str(item.get("size", "")).strip()
        if not size_text:
            continue
        if preferred_only and not bool(item.get("preferred")):
            continue
        out.append(size_text)
    return out


def catalog_nps_all() -> list[str]:
    """ASME B36.10 표준 NPS 전체 목록 (문자열, 저장 순서 유지)."""
    return _catalog_sizes("nps", preferred_only=False)


def catalog_nps_preferred() -> list[str]:
    """선호 NPS 기본값 (16개)."""
    return _catalog_sizes("nps", preferred_only=True)


def catalog_dn_all() -> list[str]:
    """ISO 6708 DN 전체 목록."""
    return _catalog_sizes("dn", preferred_only=False)


def catalog_dn_preferred() -> list[str]:
    """선호 DN 기본값 (16개)."""
    return _catalog_sizes("dn", preferred_only=True)


def catalog_sizes_all(mode: str) -> list[str]:
    """mode == 'DN' 이면 DN 전체, 그 외(NPS)이면 NPS 전체."""
    return catalog_dn_all() if str(mode).strip().upper() == "DN" else catalog_nps_all()


def catalog_sizes_preferred(mode: str) -> list[str]:
    """mode == 'DN' 이면 선호 DN, 그 외(NPS)이면 선호 NPS."""
    return catalog_dn_preferred() if str(mode).strip().upper() == "DN" else catalog_nps_preferred()


# ---------------------------------------------------------------------------
# Class-layer reference data (design codes, nominal-size systems, unit systems)
# ---------------------------------------------------------------------------

def _load_reference(path: Path) -> dict[str, Any]:
    logger = logging.getLogger(__name__)
    return _read_json_dict(path, logger)


def load_design_codes() -> dict[str, Any]:
    """`data/design_codes.json` 원본 dict 반환."""
    return _load_reference(design_codes_path())


def load_nominal_size_systems() -> dict[str, Any]:
    """`data/nominal_size_systems.json` 원본 dict 반환."""
    return _load_reference(nominal_size_systems_path())


def load_unit_systems() -> dict[str, Any]:
    """`data/unit_systems.json` 원본 dict 반환."""
    return _load_reference(unit_systems_path())


def design_codes_allowed() -> list[str]:
    """Class 계층에서 선택 가능한 설계 코드 목록."""
    raw = load_design_codes().get("allowed", [])
    return [str(x) for x in raw if str(x).strip()]


def nominal_size_systems_allowed() -> list[str]:
    """Class 계층에서 선택 가능한 공칭 사이즈 체계 (NPS/DN)."""
    raw = load_nominal_size_systems().get("allowed", [])
    return [str(x) for x in raw if str(x).strip()]


def unit_systems_allowed() -> list[str]:
    """Class Template Unit_System 시트에서 선택 가능한 단위 체계 (Metric/Imperial)."""
    raw = load_unit_systems().get("allowed", [])
    return [str(x) for x in raw if str(x).strip()]


def design_units_for(system: str) -> dict[str, Any]:
    """선택된 unit system 의 temperature·pressure 옵션 블록을 반환."""
    blk = load_unit_systems().get("design_units", {})
    if not isinstance(blk, dict):
        return {}
    sub = blk.get(str(system).strip())
    return sub if isinstance(sub, dict) else {}


# ---------------------------------------------------------------------------
# NPS ↔ DN pairing (Global Setting Size Selection display)
# ---------------------------------------------------------------------------

_NPS_DN_PAIRING_CACHE: list[dict[str, str]] | None = None


def load_nps_dn_pairs() -> list[dict[str, str]]:
    """`data/nps_dn_pairing.json` 의 1:1 페어 목록.

    각 항목은 {"nps": "<size>", "dn": "<size>"} 형태이며, 짝이 없는 경우 "-".
    저장된 순서를 그대로 유지(ASME B36.10 / ISO 6708 카탈로그 순).
    """
    global _NPS_DN_PAIRING_CACHE
    if _NPS_DN_PAIRING_CACHE is not None:
        return [dict(p) for p in _NPS_DN_PAIRING_CACHE]
    raw = _load_reference(nps_dn_pairing_path())
    pairs_raw = raw.get("pairs") if isinstance(raw, dict) else []
    out: list[dict[str, str]] = []
    if isinstance(pairs_raw, list):
        for item in pairs_raw:
            if not isinstance(item, dict):
                continue
            nps = str(item.get("nps", "")).strip()
            dn = str(item.get("dn", "")).strip()
            out.append({"nps": nps, "dn": dn})
    _NPS_DN_PAIRING_CACHE = out
    return [dict(p) for p in out]
