"""클래스 수준 템플릿 입력 — GUI에서 수집 후 워크북에 기록."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import config


@dataclass
class SizeTableRow:
    size1: str
    size2: str
    item_type: str
    remarks: str = ""


@dataclass
class NamedSizeTable:
    """Reducing_Table 또는 Branch_Table 시트에 기록되는 하나의 표(Table_Code)."""

    table_code: str
    rows: list[SizeTableRow] = field(default_factory=list)


@dataclass
class ClassLevelBundle:
    """템플릿 xlsx의 클래스 수준 시트 내용."""

    class_define_rows: list[dict[str, str]]
    fluid_service_rows: list[dict[str, str]]
    joint_rows: list[dict[str, str]]
    schedule_rows: list[dict[str, str]]
    reducing_tables: list[NamedSizeTable]
    branch_tables: list[NamedSizeTable]

    def all_table_codes(self) -> list[str]:
        return [t.table_code.strip() for t in self.reducing_tables + self.branch_tables]

    def validate(self) -> list[str]:
        """Empty list means OK. Error strings for the wizard (English)."""
        errs: list[str] = []
        codes = [c for c in self.all_table_codes() if c]
        if len(codes) != len(set(codes)):
            errs.append(
                "Duplicate Table_Code. Names must be unique across all reducing and branch tables."
            )
        if any(not t.table_code.strip() for t in self.reducing_tables + self.branch_tables):
            errs.append("Table_Code (table name) cannot be blank.")

        r_codes = {t.table_code.strip() for t in self.reducing_tables}
        b_codes = {t.table_code.strip() for t in self.branch_tables}
        for i, row in enumerate(self.class_define_rows):
            label = f"Class_Define row {i + 1}"
            cn = (row.get("Class_Name") or "").strip()
            if not cn:
                errs.append(f"{label}: Class_Name is required.")
            for col, allowed in (
                ("Reducing_Table_1", r_codes),
                ("Reducing_Table_2", r_codes),
            ):
                v = (row.get(col) or "").strip()
                if v and v not in allowed:
                    errs.append(
                        f"{label}: {col} value {v!r} is not a registered reducing table name."
                    )
            for col, allowed in (
                ("Branch_Table_1", b_codes),
                ("Branch_Table_2", b_codes),
            ):
                v = (row.get(col) or "").strip()
                if v and v not in allowed:
                    errs.append(
                        f"{label}: {col} value {v!r} is not a registered branch table name."
                    )
            ca_raw = str(row.get("Corrosion_Allowance", "") or "").strip()
            if ca_raw:
                try:
                    float(ca_raw)
                except ValueError:
                    errs.append(f"{label}: Corrosion_Allowance must be numeric; got {ca_raw!r}.")
            else:
                policy = str(
                    config.config_manager.get(
                        "validation_policy.corrosion_allowance.empty_value_policy",
                        "warning",
                    )
                    or "warning"
                ).strip().lower()
                if policy == "error":
                    errs.append(f"{label}: Corrosion_Allowance is required.")
        return errs

    def validation_warnings(self) -> list[str]:
        warns: list[str] = []
        policy = str(
            config.config_manager.get(
                "validation_policy.corrosion_allowance.empty_value_policy",
                "warning",
            )
            or "warning"
        ).strip().lower()
        if policy != "warning":
            return warns
        for i, row in enumerate(self.class_define_rows):
            ca_raw = str(row.get("Corrosion_Allowance", "") or "").strip()
            if ca_raw:
                continue
            label = f"Class_Define row {i + 1}"
            warns.append(f"{label}: Corrosion_Allowance is empty.")
        return warns


def row_dict_for_headers(headers: list[str], data: dict[str, Any] | None = None) -> dict[str, str]:
    d = data or {}
    return {h: str(d.get(h, "") or "") for h in headers}
