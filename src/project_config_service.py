"""프로젝트 설정(config/project/) 로드·검증·저장·백업·재로드 서비스."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import config
from project_constraints import validate_project_constraints


# ---------------------------------------------------------------------------
# Allowed-list definitions (SSOT for the settings dialog dropdowns)
# ---------------------------------------------------------------------------

UNIT_SYSTEM_OPTIONS = ("Metric", "Imperial")
NOMINAL_SIZE_OPTIONS = ("NPS", "DN")
PIPE_THREAD_OPTIONS = ("NPT", "PT")
BOLT_THREAD_OPTIONS = ("Metric", "Imperial")
DESIGN_CODE_OPTIONS = ("ASME B31.3", "ASME B31.4")

METRIC_TEMPERATURE_OPTIONS = ("°C",)
IMPERIAL_TEMPERATURE_OPTIONS = ("°F",)
METRIC_PRESSURE_OPTIONS = ("bar", "barg", "kPa", "MPa")
IMPERIAL_PRESSURE_OPTIONS = ("psig", "psi", "psia")


def _design_unit_options(
    unit_system: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return (temperature_options, pressure_options) for the given unit system."""
    if unit_system == "Imperial":
        return IMPERIAL_TEMPERATURE_OPTIONS, IMPERIAL_PRESSURE_OPTIONS
    return METRIC_TEMPERATURE_OPTIONS, METRIC_PRESSURE_OPTIONS


# ---------------------------------------------------------------------------
# Data class: editable project settings (flat view of the three JSON files)
# ---------------------------------------------------------------------------

class ProjectSettings:
    """Flat, immutable-style value object for the editable project settings."""

    __slots__ = (
        "unit_system",
        "temperature_unit",
        "pressure_unit",
        "nominal_size",
        "pipe_thread",
        "bolt_thread",
        "design_code",
    )

    def __init__(
        self,
        *,
        unit_system: str = "Metric",
        temperature_unit: str = "°C",
        pressure_unit: str = "bar",
        nominal_size: str = "NPS",
        pipe_thread: str = "NPT",
        bolt_thread: str = "Metric",
        design_code: str = "ASME B31.3",
    ) -> None:
        self.unit_system = unit_system
        self.temperature_unit = temperature_unit
        self.pressure_unit = pressure_unit
        self.nominal_size = nominal_size
        self.pipe_thread = pipe_thread
        self.bolt_thread = bolt_thread
        self.design_code = design_code


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_current_settings() -> ProjectSettings:
    """현재 config_manager 에서 편집 대상 값만 추출합니다."""
    snap = config.config_manager.snapshot()
    un = snap.get("units_notation", {})
    us_block = un.get("unit_system", {})
    selected_system = str(us_block.get("selected", "Metric") or "Metric").strip()

    du = us_block.get("design_units", {})
    sys_du = du.get(selected_system, {})
    temp_sel = ""
    press_sel = ""
    t_block = sys_du.get("temperature", {})
    if isinstance(t_block, dict):
        temp_sel = str(t_block.get("selected", "") or "").strip()
    p_block = sys_du.get("pressure", {})
    if isinstance(p_block, dict):
        press_sel = str(p_block.get("selected", "") or "").strip()

    ns = un.get("nominal_size", {})
    pt = un.get("pipe_thread", {})
    bt = un.get("bolt_thread", {})
    pdc = snap.get("piping_design_codes", {})

    return ProjectSettings(
        unit_system=selected_system,
        temperature_unit=temp_sel,
        pressure_unit=press_sel,
        nominal_size=str(ns.get("selected", "NPS") or "NPS").strip(),
        pipe_thread=str(pt.get("selected", "NPT") or "NPT").strip(),
        bolt_thread=str(bt.get("selected", "Metric") or "Metric").strip(),
        design_code=str(pdc.get("selected", "ASME B31.3") or "ASME B31.3").strip(),
    )


# ---------------------------------------------------------------------------
# Validate (before saving)
# ---------------------------------------------------------------------------

def validate_settings(settings: ProjectSettings) -> list[str]:
    """드롭다운 선택값이 허용 목록에 있는지 확인합니다."""
    errors: list[str] = []
    if settings.unit_system not in UNIT_SYSTEM_OPTIONS:
        errors.append(f"단위 체계: {settings.unit_system!r} 는 허용되지 않습니다.")
    if settings.nominal_size not in NOMINAL_SIZE_OPTIONS:
        errors.append(f"공칭 사이즈: {settings.nominal_size!r} 는 허용되지 않습니다.")
    if settings.pipe_thread not in PIPE_THREAD_OPTIONS:
        errors.append(f"파이프 나사: {settings.pipe_thread!r} 는 허용되지 않습니다.")
    if settings.bolt_thread not in BOLT_THREAD_OPTIONS:
        errors.append(f"볼트 나사: {settings.bolt_thread!r} 는 허용되지 않습니다.")
    if settings.design_code not in DESIGN_CODE_OPTIONS:
        errors.append(f"설계 코드: {settings.design_code!r} 는 허용되지 않습니다.")

    temp_opts, press_opts = _design_unit_options(settings.unit_system)
    if settings.temperature_unit not in temp_opts:
        errors.append(f"온도 단위: {settings.temperature_unit!r} 는 허용되지 않습니다.")
    if settings.pressure_unit not in press_opts:
        errors.append(f"압력 단위: {settings.pressure_unit!r} 는 허용되지 않습니다.")

    return errors


# ---------------------------------------------------------------------------
# Backup + Save + Reload
# ---------------------------------------------------------------------------

_BACKUP_SUFFIX = ".bak"


def _backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_suffix(f".{stamp}{_BACKUP_SUFFIX}")
    shutil.copy2(path, backup)
    return backup


def _write_json_atomic(path: Path, obj: Any) -> None:
    """임시 파일 → rename 으로 원자적 저장."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def save_and_reload(settings: ProjectSettings) -> list[str]:
    """
    검증 → 백업 → 저장 → config_manager 재로드.
    반환: 검증 오류 목록 (비어 있으면 성공).
    """
    errors = validate_settings(settings)
    if errors:
        return errors

    proj_dir = config.project_config_dir()

    # --- units_notation.json ---
    un_path = proj_dir / "units_notation.json"
    un_current = _read_existing_json(un_path)
    un_new = _build_units_notation(settings, un_current)
    _backup_file(un_path)
    _write_json_atomic(un_path, un_new)

    # --- piping_design_codes.json ---
    pdc_path = proj_dir / "piping_design_codes.json"
    pdc_current = _read_existing_json(pdc_path)
    pdc_new = {**pdc_current, "selected": settings.design_code}
    if "allowed" not in pdc_new or not isinstance(pdc_new["allowed"], list):
        pdc_new["allowed"] = list(DESIGN_CODE_OPTIONS)
    _backup_file(pdc_path)
    _write_json_atomic(pdc_path, pdc_new)

    # --- reload ---
    constraint_warnings = config.config_manager.reload()
    return constraint_warnings


def _read_existing_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _build_units_notation(
    settings: ProjectSettings,
    current: dict[str, Any],
) -> dict[str, Any]:
    """현재 JSON 을 기반으로 selected 값만 교체한 새 dict 를 반환합니다."""
    us = dict(current.get("unit_system", {}))
    us["selected"] = settings.unit_system
    us["allowed"] = list(UNIT_SYSTEM_OPTIONS)

    du = dict(us.get("design_units", {}))
    for sys_name in ("Metric", "Imperial"):
        sys_block = dict(du.get(sys_name, {}))
        t_opts, p_opts = _design_unit_options(sys_name)

        t = dict(sys_block.get("temperature", {}))
        t["allowed"] = list(t_opts)
        if sys_name == settings.unit_system:
            t["selected"] = settings.temperature_unit

        p = dict(sys_block.get("pressure", {}))
        p["allowed"] = list(p_opts)
        if sys_name == settings.unit_system:
            p["selected"] = settings.pressure_unit

        sys_block["temperature"] = t
        sys_block["pressure"] = p
        du[sys_name] = sys_block

    us["design_units"] = du

    ns = dict(current.get("nominal_size", {}))
    ns["allowed"] = list(NOMINAL_SIZE_OPTIONS)
    ns["selected"] = settings.nominal_size

    pt = dict(current.get("pipe_thread", {}))
    pt["allowed"] = list(PIPE_THREAD_OPTIONS)
    pt["selected"] = settings.pipe_thread

    bt = dict(current.get("bolt_thread", {}))
    bt["allowed"] = list(BOLT_THREAD_OPTIONS)
    bt["selected"] = settings.bolt_thread

    return {
        "unit_system": us,
        "nominal_size": ns,
        "pipe_thread": pt,
        "bolt_thread": bt,
    }
