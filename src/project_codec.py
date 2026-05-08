"""ClassLevelBundle ↔ JSON codec.

source-of-truth project files are plain JSON. xlsx is only ever an
export artifact (see template_generator). This module owns the
in-memory bundle ↔ on-disk JSON conversion.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from class_level_model import (
    ClassLevelBundle,
    ClassTemplateGlobalSettings,
    NamedSizeTable,
    SizeSelection,
    SizeTableRow,
    default_size_selection_from_catalog,
)


SCHEMA_VERSION = 1


class ProjectFileError(ValueError):
    """JSON 프로젝트 파일을 읽거나 해석할 수 없을 때."""


def bundle_to_json_dict(bundle: ClassLevelBundle) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "global_settings": _global_settings_to_dict(bundle.global_settings),
        "class_define_rows": [dict(r) for r in bundle.class_define_rows],
        "schedule_rows": [dict(r) for r in bundle.schedule_rows],
        "reducing_tables": [_named_size_table_to_dict(t) for t in bundle.reducing_tables],
        "branch_tables": [_named_size_table_to_dict(t) for t in bundle.branch_tables],
        "component_rows": {
            sheet: [dict(r) for r in rows]
            for sheet, rows in bundle.component_rows.items()
        },
    }


def bundle_from_json_dict(data: dict[str, Any]) -> ClassLevelBundle:
    if not isinstance(data, dict):
        raise ProjectFileError("Project JSON root must be an object.")
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ProjectFileError(
            f"Unsupported project schema_version {version!r}; expected {SCHEMA_VERSION}."
        )
    return ClassLevelBundle(
        class_define_rows=_string_rows(data.get("class_define_rows")),
        schedule_rows=_string_rows(data.get("schedule_rows")),
        reducing_tables=_named_size_tables_from(data.get("reducing_tables")),
        branch_tables=_named_size_tables_from(data.get("branch_tables")),
        global_settings=_global_settings_from(data.get("global_settings")),
        component_rows=_component_rows_from(data.get("component_rows")),
    )


def save_project(bundle: ClassLevelBundle, path: Path | str) -> Path:
    """JSON 파일에 원자적으로 기록한다 (tmp → rename)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = bundle_to_json_dict(bundle)
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=target.name + ".", suffix=".tmp", dir=str(target.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise
    return target


def load_project(path: Path | str) -> ClassLevelBundle:
    p = Path(path)
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as e:
        raise ProjectFileError(f"Project file not found: {p}") from e
    except json.JSONDecodeError as e:
        raise ProjectFileError(f"Project file is not valid JSON: {p} ({e.msg})") from e
    return bundle_from_json_dict(data)


# ── helpers ────────────────────────────────────────────────────────────────────


def _global_settings_to_dict(gs: ClassTemplateGlobalSettings) -> dict[str, Any]:
    return {
        "unit_system": gs.unit_system or "",
        "design_temperature_unit": gs.design_temperature_unit or "",
        "design_pressure_unit": gs.design_pressure_unit or "",
        "size_selection": {
            "nps": list(gs.size_selection.nps),
            "dn": list(gs.size_selection.dn),
        },
    }


def _global_settings_from(raw: Any) -> ClassTemplateGlobalSettings:
    if not isinstance(raw, dict):
        return ClassTemplateGlobalSettings(
            size_selection=default_size_selection_from_catalog()
        )
    sel_raw = raw.get("size_selection") if isinstance(raw.get("size_selection"), dict) else {}
    nps = [str(s) for s in (sel_raw.get("nps") or []) if str(s).strip()]
    dn = [str(s) for s in (sel_raw.get("dn") or []) if str(s).strip()]
    selection = SizeSelection(nps=nps, dn=dn) if (nps or dn) else default_size_selection_from_catalog()
    return ClassTemplateGlobalSettings(
        unit_system=str(raw.get("unit_system") or ""),
        design_temperature_unit=str(raw.get("design_temperature_unit") or ""),
        design_pressure_unit=str(raw.get("design_pressure_unit") or ""),
        size_selection=selection,
    )


def _named_size_table_to_dict(table: NamedSizeTable) -> dict[str, Any]:
    return {
        "table_code": table.table_code,
        "nominal_mode": table.nominal_mode or "",
        "size_from": table.size_from or "",
        "size_to": table.size_to or "",
        "rows": [
            {
                "size1": r.size1,
                "size2": r.size2,
                "item_type": r.item_type,
                "remarks": r.remarks,
            }
            for r in table.rows
        ],
    }


def _named_size_tables_from(raw: Any) -> list[NamedSizeTable]:
    if not isinstance(raw, list):
        return []
    out: list[NamedSizeTable] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        rows_raw = item.get("rows") if isinstance(item.get("rows"), list) else []
        rows: list[SizeTableRow] = []
        for r in rows_raw:
            if not isinstance(r, dict):
                continue
            rows.append(
                SizeTableRow(
                    size1=str(r.get("size1") or ""),
                    size2=str(r.get("size2") or ""),
                    item_type=str(r.get("item_type") or ""),
                    remarks=str(r.get("remarks") or ""),
                )
            )
        out.append(
            NamedSizeTable(
                table_code=str(item.get("table_code") or ""),
                rows=rows,
                nominal_mode=str(item.get("nominal_mode") or ""),
                size_from=str(item.get("size_from") or ""),
                size_to=str(item.get("size_to") or ""),
            )
        )
    return out


def _string_rows(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        out.append({str(k): ("" if v is None else str(v)) for k, v in r.items()})
    return out


def _component_rows_from(raw: Any) -> dict[str, list[dict[str, str]]]:
    if not isinstance(raw, dict):
        return {}
    return {str(sheet): _string_rows(rows) for sheet, rows in raw.items()}
