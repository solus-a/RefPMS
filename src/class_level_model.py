"""클래스 수준 템플릿 입력 — GUI에서 수집 후 워크북에 기록."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import config
from excel_sheet_utils import build_header_index, detect_header_row, get_cell_text

ASME_SCHEDULE_VALUES: tuple[str, ...] = (
    "SCH5",
    "SCH10",
    "SCH20",
    "SCH30",
    "SCH40",
    "SCH60",
    "SCH80",
    "SCH100",
    "SCH120",
    "SCH140",
    "SCH160",
    "SCH5S",
    "SCH10S",
    "SCH40S",
    "SCH80S",
    "STD",
    "XS",
    "XXS",
)


def normalizeScheduleValue(raw: str) -> str:
    value = str(raw or "").strip().upper()
    if not value:
        return ""
    if value.startswith("SCH"):
        return value
    if value.startswith("S") and value[1:].isdigit():
        return f"SCH{value[1:]}"
    if value.isdigit():
        return f"SCH{value}"
    return value


def scheduleAllowlist() -> tuple[str, ...]:
    return ASME_SCHEDULE_VALUES


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
    nominal_mode: str = ""  # "NPS" or "DN"; set once on creation, immutable after


@dataclass
class ClassSizeRange:
    """Class-level Size Range: 이 클래스에서 활성화된 공칭 사이즈 부분집합 (Class Constraint)."""

    class_name: str
    active_sizes: list[str] = field(default_factory=list)


@dataclass
class ClassTemplateGlobalSettings:
    """Class Template 전역 설정 (Unit_System 시트). 모든 Class 에 공통 적용."""

    unit_system: str = ""
    design_temperature_unit: str = ""
    design_pressure_unit: str = ""


UNIT_SYSTEM_SHEET = "Unit_System"
UNIT_SYSTEM_HEADERS = [
    "Unit_System",
    "Design_Temperature_Unit",
    "Design_Pressure_Unit",
]


_LEGACY_UNIT_SYSTEM_ALIASES = {
    "Metric": "SI",
    "Imperial": "US Customary",
}


def _normalize_unit_system_value(raw: str) -> str:
    """레거시 템플릿의 Metric/Imperial 값을 현행 SI / US Customary 로 정규화."""
    v = (raw or "").strip()
    return _LEGACY_UNIT_SYSTEM_ALIASES.get(v, v)


def read_global_settings_from_workbook(workbook) -> ClassTemplateGlobalSettings:
    """Class Template 워크북의 Unit_System 시트에서 전역 설정을 로드.

    시트가 없거나 헤더가 맞지 않으면 빈 설정을 반환 (빈 템플릿/레거시 대응).
    """
    if UNIT_SYSTEM_SHEET not in workbook.sheetnames:
        return ClassTemplateGlobalSettings()
    ws = workbook[UNIT_SYSTEM_SHEET]
    try:
        header_row = detect_header_row(ws, UNIT_SYSTEM_HEADERS)
    except ValueError:
        return ClassTemplateGlobalSettings()
    htc = build_header_index(ws, header_row)
    if any(h not in htc for h in UNIT_SYSTEM_HEADERS):
        return ClassTemplateGlobalSettings()
    data_row = header_row + 1
    return ClassTemplateGlobalSettings(
        unit_system=_normalize_unit_system_value(
            get_cell_text(ws, data_row, htc, "Unit_System")
        ),
        design_temperature_unit=get_cell_text(ws, data_row, htc, "Design_Temperature_Unit"),
        design_pressure_unit=get_cell_text(ws, data_row, htc, "Design_Pressure_Unit"),
    )


@dataclass
class ClassLevelBundle:
    """템플릿 xlsx의 클래스 수준 시트 내용."""

    class_define_rows: list[dict[str, str]]
    schedule_rows: list[dict[str, str]]
    reducing_tables: list[NamedSizeTable]
    branch_tables: list[NamedSizeTable]
    size_ranges: list[ClassSizeRange] = field(default_factory=list)
    global_settings: ClassTemplateGlobalSettings = field(
        default_factory=ClassTemplateGlobalSettings
    )

    def all_table_codes(self) -> list[str]:
        return [t.table_code.strip() for t in self.reducing_tables + self.branch_tables]

    def active_sizes_for(self, class_name: str) -> list[str]:
        """주어진 Class_Name 의 활성 사이즈 목록. 엔트리 없으면 빈 리스트."""
        target = (class_name or "").strip()
        for sr in self.size_ranges:
            if (sr.class_name or "").strip() == target:
                return [str(s).strip() for s in sr.active_sizes if str(s).strip()]
        return []

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

        class_nominal: dict[str, str] = {}
        for row in self.class_define_rows:
            name = (row.get("Class_Name") or "").strip()
            if not name:
                continue
            class_nominal[name] = (row.get("Nominal_Size_System") or "").strip() or "NPS"

        class_names_seen: set[str] = set()
        for i, sr in enumerate(self.size_ranges):
            label = f"Class_Size_Range row {i + 1}"
            cname = (sr.class_name or "").strip()
            if not cname:
                errs.append(f"{label}: Class_Name is required.")
                continue
            if cname in class_names_seen:
                errs.append(f"{label}: duplicate Class_Name {cname!r}.")
            class_names_seen.add(cname)
            mode = class_nominal.get(cname, "NPS")
            catalog_sizes = set(config.catalog_sizes_all(mode))
            for sz in sr.active_sizes:
                t = str(sz).strip()
                if t and catalog_sizes and t not in catalog_sizes:
                    errs.append(
                        f"{label}: size {t!r} is not in the {mode} standard catalog."
                    )

        allowed_schedule_values = set(scheduleAllowlist())

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

        for i, row in enumerate(self.schedule_rows):
            label = f"Schedule row {i + 1}"
            size_from_raw = str(row.get("Size_From", "") or "").strip()
            size_to_raw = str(row.get("Size_To", "") or "").strip()
            schedule_raw = str(row.get("Schedule", "") or "").strip()
            schedule_normalized = normalizeScheduleValue(schedule_raw)

            if size_from_raw:
                try:
                    float(size_from_raw)
                except ValueError:
                    errs.append(f"{label}: Size_From must be numeric; got {size_from_raw!r}.")
            if size_to_raw:
                try:
                    float(size_to_raw)
                except ValueError:
                    errs.append(f"{label}: Size_To must be numeric; got {size_to_raw!r}.")
            if size_from_raw and size_to_raw:
                try:
                    if float(size_to_raw) < float(size_from_raw):
                        errs.append(
                            f"{label}: Size_To must be greater than or equal to Size_From."
                        )
                except ValueError:
                    # Numeric-format errors are already reported above.
                    pass
            if schedule_normalized and schedule_normalized not in allowed_schedule_values:
                errs.append(
                    f"{label}: Schedule value {schedule_raw!r} is not allowed."
                )
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
