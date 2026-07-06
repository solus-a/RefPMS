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
    """Reducing_Table 또는 Branch_Table 시트에 기록되는 하나의 표(Table_Code).

    size_from / size_to: 이 표가 다루는 사이즈 범위 (양 끝점, 두 축 공통).
    실제 매트릭스 행/열은 (size_from..size_to) ∩ Global Size Selection.
    """

    table_code: str
    rows: list[SizeTableRow] = field(default_factory=list)
    nominal_mode: str = ""  # "NPS" or "DN"; set once on creation, immutable after
    size_from: str = ""
    size_to: str = ""


@dataclass
class SizeSelection:
    """Class Template 전역 — 사용 가능 사이즈 부분집합 (Global Size Selection).

    NPS / DN 각각 카탈로그의 부분집합. 빈 리스트면 "전부 사용" 으로 간주(레거시 호환).
    Class·Reducing·Branch 의 Size_From/Size_To 드롭다운은 이 목록만 보여준다.
    """

    nps: list[str] = field(default_factory=list)
    dn: list[str] = field(default_factory=list)

    def for_mode(self, mode: str) -> list[str]:
        m = (mode or "").strip().upper()
        return list(self.dn) if m == "DN" else list(self.nps)


# 필수 필드의 SSOT 는 domain_schema.CLASS_DEFINE_FIELDS 의 required 플래그.
# Class_Name 은 제외 — class_define_missing_fields 가 이름으로 행을 찾는 구조라
# 별도 경로(validate 의 비어있음 검사)에서 다룬다.
import domain_schema as _domain_schema

CLASS_DEFINE_REQUIRED_FIELDS: tuple[str, ...] = tuple(
    f for f in _domain_schema.class_define_required_fields() if f != "Class_Name"
)


def _parse_signed_decimal(value: str | None) -> float | None:
    raw = (value or "").strip()
    if not raw or raw == "-":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def component_row_size_pair_errors(
    sheet_name: str, values: dict[str, str]
) -> list[str]:
    """Component row 의 size pair (From <= To) 검증.

    빈 리스트 = OK. 현재 Pipe_Group 만 정책 정의됨; 다른 시트는 그 시트 작업 시 보강.
    """
    if sheet_name != "Pipe_Group":
        return []
    sf = (values.get("Size_From") or "").strip()
    st = (values.get("Size_To") or "").strip()
    if not sf or not st:
        return []
    try:
        if float(sf) > float(st):
            return [f"Size_From ({sf}) > Size_To ({st})"]
    except ValueError:
        return []
    return []


def component_row_missing_required(
    sheet_name: str, values: dict[str, str]
) -> list[str]:
    """Component row 의 그룹별 필수 필드 검증. 빈 리스트 = OK.

    필수 정의의 단일 소스는 data_defaults.DEFAULT_COMPONENT_MAPPING
    (required_non_empty + conditional_required). 폼에 존재하지 않는 필드
    (예: Class_Name 은 저장 단계에서 채워짐)는 건너뛴다.
    """
    from data_defaults import DEFAULT_COMPONENT_MAPPING

    rules = (DEFAULT_COMPONENT_MAPPING.get("sheets") or {}).get(sheet_name)
    if not isinstance(rules, dict):
        return []

    def _filled(field_name: str) -> bool:
        return bool((values.get(field_name) or "").strip())

    missing: list[str] = []
    for field_name in rules.get("required_non_empty", []):
        if field_name not in values:
            continue
        if not _filled(field_name):
            missing.append(field_name)

    for cond in rules.get("conditional_required", []):
        if not isinstance(cond, dict):
            continue
        when_field = cond.get("when_field")
        if not when_field or when_field not in values:
            continue
        allowed = {str(v).strip().upper() for v in (cond.get("when_values") or [])}
        if allowed and (values.get(when_field) or "").strip().upper() not in allowed:
            continue
        for req in cond.get("require_non_empty", []):
            if req in values and not _filled(req) and req not in missing:
                missing.append(req)

    return missing


def component_row_required_fields(sheet_name: str) -> frozenset[str]:
    """그룹의 무조건 필수 필드 집합 (required_non_empty). UI 에서 (None) 옵션을
    줄지 여부 판단에 사용 — 필수 필드에는 (None) 선택지를 두지 않는다.
    conditional_required(예: Flange FR Size2)는 항상 필수는 아니므로 제외."""
    from data_defaults import DEFAULT_COMPONENT_MAPPING

    rules = (DEFAULT_COMPONENT_MAPPING.get("sheets") or {}).get(sheet_name)
    if not isinstance(rules, dict):
        return frozenset()
    return frozenset(rules.get("required_non_empty", []))


@dataclass
class ClassTemplateGlobalSettings:
    """Class Template 전역 설정 (Unit_System + Size_Selection 시트). 모든 Class 에 공통 적용."""

    unit_system: str = ""
    design_temperature_unit: str = ""
    design_pressure_unit: str = ""
    size_selection: SizeSelection = field(default_factory=SizeSelection)


UNIT_SYSTEM_SHEET = "Unit_System"
UNIT_SYSTEM_HEADERS = [
    "Unit_System",
    "Design_Temperature_Unit",
    "Design_Pressure_Unit",
]

SIZE_SELECTION_SHEET = "Size_Selection"
SIZE_SELECTION_HEADERS = ["NPS", "DN", "Use"]


_LEGACY_UNIT_SYSTEM_ALIASES = {
    "Metric": "SI",
    "Imperial": "US Customary",
}


def _normalize_unit_system_value(raw: str) -> str:
    """레거시 템플릿의 Metric/Imperial 값을 현행 SI / US Customary 로 정규화."""
    v = (raw or "").strip()
    return _LEGACY_UNIT_SYSTEM_ALIASES.get(v, v)


def _truthy_use(raw: str) -> bool:
    v = (raw or "").strip().lower()
    return v in ("1", "true", "yes", "y", "x", "o", "on", "v", "✓", "체크")


def default_size_selection_from_catalog() -> SizeSelection:
    """기본 Size_Selection — preferred=True 인 사이즈만 활성."""
    return SizeSelection(
        nps=list(config.catalog_nps_preferred()),
        dn=list(config.catalog_dn_preferred()),
    )


def read_size_selection_from_workbook(workbook) -> SizeSelection | None:
    """Size_Selection 시트에서 사용자가 저장한 활성 NPS/DN 목록을 로드.

    시트가 없거나 헤더가 맞지 않으면 None 반환 (호출 측에서 기본값을 적용).
    """
    if SIZE_SELECTION_SHEET not in workbook.sheetnames:
        return None
    ws = workbook[SIZE_SELECTION_SHEET]
    try:
        header_row = detect_header_row(ws, SIZE_SELECTION_HEADERS)
    except ValueError:
        return None
    htc = build_header_index(ws, header_row)
    if any(h not in htc for h in SIZE_SELECTION_HEADERS):
        return None
    nps_active: list[str] = []
    dn_active: list[str] = []
    for r in range(header_row + 1, ws.max_row + 1):
        nps_v = get_cell_text(ws, r, htc, "NPS").strip()
        dn_v = get_cell_text(ws, r, htc, "DN").strip()
        use_v = get_cell_text(ws, r, htc, "Use").strip()
        if not _truthy_use(use_v):
            continue
        if nps_v and nps_v != "-":
            nps_active.append(nps_v)
        if dn_v and dn_v != "-":
            dn_active.append(dn_v)
    return SizeSelection(nps=nps_active, dn=dn_active)


def read_global_settings_from_workbook(workbook) -> ClassTemplateGlobalSettings:
    """Class Template 워크북의 Unit_System + Size_Selection 시트에서 전역 설정을 로드.

    시트가 없거나 헤더가 맞지 않으면 빈 설정을 반환 (빈 템플릿/레거시 대응).
    """
    sel = read_size_selection_from_workbook(workbook)
    if sel is None:
        sel = default_size_selection_from_catalog()
    if UNIT_SYSTEM_SHEET not in workbook.sheetnames:
        return ClassTemplateGlobalSettings(size_selection=sel)
    ws = workbook[UNIT_SYSTEM_SHEET]
    try:
        header_row = detect_header_row(ws, UNIT_SYSTEM_HEADERS)
    except ValueError:
        return ClassTemplateGlobalSettings(size_selection=sel)
    htc = build_header_index(ws, header_row)
    if any(h not in htc for h in UNIT_SYSTEM_HEADERS):
        return ClassTemplateGlobalSettings(size_selection=sel)
    data_row = header_row + 1
    return ClassTemplateGlobalSettings(
        unit_system=_normalize_unit_system_value(
            get_cell_text(ws, data_row, htc, "Unit_System")
        ),
        design_temperature_unit=get_cell_text(ws, data_row, htc, "Design_Temperature_Unit"),
        design_pressure_unit=get_cell_text(ws, data_row, htc, "Design_Pressure_Unit"),
        size_selection=sel,
    )


@dataclass
class ClassLevelBundle:
    """템플릿 xlsx의 클래스 수준 시트 내용.

    class_define_rows의 dict 키는 단위에 무관한 storage 키
    (`Design_Temperature_From`, `Design_Pressure_From` 등) 를 사용한다.
    xlsx 컬럼 헤더(`Design_Temperature_From [°C]`)는 export/import 경계에서만
    변환되며 모델 내부 어디에서도 사용하지 않는다.
    """

    class_define_rows: list[dict[str, str]]
    schedule_rows: list[dict[str, str]]
    reducing_tables: list[NamedSizeTable]
    branch_tables: list[NamedSizeTable]
    global_settings: ClassTemplateGlobalSettings = field(
        default_factory=ClassTemplateGlobalSettings
    )
    component_rows: dict[str, list[dict[str, str]]] = field(default_factory=dict)

    def all_table_codes(self) -> list[str]:
        return [t.table_code.strip() for t in self.reducing_tables + self.branch_tables]

    def active_sizes_for_class(self, class_name: str) -> list[str]:
        """주어진 Class_Name 의 활성 사이즈 목록.
        (Class_Define 의 Size_From / Size_To) ∩ (Global Size Selection, 해당 모드).
        """
        target = (class_name or "").strip()
        for row in self.class_define_rows:
            if (row.get("Class_Name") or "").strip() != target:
                continue
            mode = (row.get("Nominal_Size_System") or "NPS").strip() or "NPS"
            sf = (row.get("Size_From") or "").strip()
            st = (row.get("Size_To") or "").strip()
            return _resolve_active_sizes(self.global_settings.size_selection, mode, sf, st)
        return []

    def class_define_value_errors(self, class_name: str) -> list[str]:
        """Class_Define cross-field 검증 (Design_Temperature/Pressure From > To 등).

        Empty list means OK. The class_name is matched against Class_Define rows.
        """
        row = next(
            (r for r in self.class_define_rows
             if (r.get("Class_Name") or "").strip() == class_name),
            None,
        )
        if row is None:
            return []
        errors: list[str] = []

        def check_pair(from_h: str, to_h: str, label: str) -> None:
            fv = _parse_signed_decimal(row.get(from_h, ""))
            tv = _parse_signed_decimal(row.get(to_h, ""))
            if fv is not None and tv is not None and fv > tv:
                errors.append(f"{label}: From ({fv}) > To ({tv})")

        check_pair("Design_Temperature_From", "Design_Temperature_To", "Design_Temperature")
        check_pair("Design_Pressure_From", "Design_Pressure_To", "Design_Pressure")
        return errors

    def class_define_missing_fields(self, class_name: str) -> list[str]:
        """Class_Define 필수 항목 미설정 + Schedule 행 부재 목록. Empty list means OK."""
        row = next(
            (r for r in self.class_define_rows
             if (r.get("Class_Name") or "").strip() == class_name),
            None,
        )
        if row is None:
            return ["Class not found in Class_Define"]

        missing = [
            f for f in CLASS_DEFINE_REQUIRED_FIELDS
            if not str(row.get(f, "") or "").strip()
        ]

        has_schedule = any(
            (r.get("Class_Name") or "").strip() == class_name
            for r in self.schedule_rows
        )
        if not has_schedule:
            missing.append("Schedule (no rows defined for this class)")

        return missing

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

        sel = self.global_settings.size_selection
        sel_nps = set(sel.nps)
        sel_dn = set(sel.dn)

        def _selected_for(mode: str) -> set[str]:
            return sel_dn if (mode or "").strip().upper() == "DN" else sel_nps

        class_nominal: dict[str, str] = {}
        for row in self.class_define_rows:
            name = (row.get("Class_Name") or "").strip()
            if not name:
                continue
            class_nominal[name] = (row.get("Nominal_Size_System") or "").strip() or "NPS"

        allowed_schedule_values = set(scheduleAllowlist())

        r_codes = {t.table_code.strip() for t in self.reducing_tables}
        b_codes = {t.table_code.strip() for t in self.branch_tables}

        def _norm_mode(m: str) -> str:
            x = (m or "").strip().upper()
            return "DN" if x == "DN" else "NPS"

        reducing_table_modes = {
            t.table_code.strip(): _norm_mode(t.nominal_mode)
            for t in self.reducing_tables
            if t.table_code.strip()
        }
        branch_table_modes = {
            t.table_code.strip(): _norm_mode(t.nominal_mode)
            for t in self.branch_tables
            if t.table_code.strip()
        }
        for i, row in enumerate(self.class_define_rows):
            label = f"Class_Define row {i + 1}"
            cn = (row.get("Class_Name") or "").strip()
            if not cn:
                errs.append(f"{label}: Class_Name is required.")
            mode = (row.get("Nominal_Size_System") or "NPS").strip() or "NPS"
            sf = (row.get("Size_From") or "").strip()
            st = (row.get("Size_To") or "").strip()
            allowed = _selected_for(mode)
            for col, val in (("Size_From", sf), ("Size_To", st)):
                if not val:
                    continue
                if allowed and val not in allowed:
                    errs.append(
                        f"{label}: {col} {val!r} is not in the Global Size Selection ({mode})."
                    )
            if sf and st:
                try:
                    if float(st) < float(sf):
                        errs.append(
                            f"{label}: Size_To must be greater than or equal to Size_From."
                        )
                except ValueError:
                    pass
            for col, allowed_codes in (
                ("Reducing_Table_1", r_codes),
                ("Reducing_Table_2", r_codes),
            ):
                v = (row.get(col) or "").strip()
                if v and v not in allowed_codes:
                    errs.append(
                        f"{label}: {col} value {v!r} is not a registered reducing table name."
                    )
            for col, allowed_codes in (
                ("Branch_Table_1", b_codes),
                ("Branch_Table_2", b_codes),
            ):
                v = (row.get(col) or "").strip()
                if v and v not in allowed_codes:
                    errs.append(
                        f"{label}: {col} value {v!r} is not a registered branch table name."
                    )
            class_mode_norm = _norm_mode(mode)
            for col, ref_modes in (
                ("Reducing_Table_1", reducing_table_modes),
                ("Reducing_Table_2", reducing_table_modes),
                ("Branch_Table_1", branch_table_modes),
                ("Branch_Table_2", branch_table_modes),
            ):
                v = (row.get(col) or "").strip()
                if v and v in ref_modes and ref_modes[v] != class_mode_norm:
                    errs.append(
                        f"{label}: {col} {v!r} nominal mode is {ref_modes[v]} "
                        f"but Class Nominal_Size_System is {class_mode_norm}."
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

        for tbl in self.reducing_tables + self.branch_tables:
            kind = "Reducing_Table" if tbl in self.reducing_tables else "Branch_Table"
            label = f"{kind} {tbl.table_code!r}"
            mode = (tbl.nominal_mode or "NPS").strip() or "NPS"
            allowed = _selected_for(mode)
            for col, val in (("Size_From", tbl.size_from), ("Size_To", tbl.size_to)):
                v = str(val or "").strip()
                if v and allowed and v not in allowed:
                    errs.append(
                        f"{label}: {col} {v!r} is not in the Global Size Selection ({mode})."
                    )
            if tbl.size_from and tbl.size_to:
                try:
                    if float(tbl.size_to) < float(tbl.size_from):
                        errs.append(
                            f"{label}: Size_To must be greater than or equal to Size_From."
                        )
                except ValueError:
                    pass

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


def _resolve_active_sizes(
    selection: SizeSelection, mode: str, size_from: str, size_to: str
) -> list[str]:
    """(Global Size Selection of `mode`) ∩ [size_from, size_to] — 카탈로그 순서 유지."""
    raw_pool = selection.for_mode(mode)
    if not raw_pool:
        raw_pool = list(config.catalog_sizes_all(mode))
    sf = str(size_from or "").strip()
    st = str(size_to or "").strip()
    if not sf and not st:
        return list(raw_pool)
    try:
        sfn = float(sf) if sf else None
        stn = float(st) if st else None
    except ValueError:
        return []
    out: list[str] = []
    for s in raw_pool:
        try:
            sn = float(s)
        except ValueError:
            continue
        if sfn is not None and sn < sfn:
            continue
        if stn is not None and sn > stn:
            continue
        out.append(s)
    return out


def row_dict_for_headers(headers: list[str], data: dict[str, Any] | None = None) -> dict[str, str]:
    d = data or {}
    return {h: str(d.get(h, "") or "") for h in headers}
