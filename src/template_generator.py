from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font

import config
from class_level_model import ClassLevelBundle, NamedSizeTable
from units_notation_headers import (
    class_define_headers,
    fluid_service_headers,
    read_design_units_from_merged,
)
from data_defaults import DEFAULT_CLASS_MATERIAL_MAPPING, DEFAULT_COMPONENT_MAPPING
from excel_sheet_utils import build_header_index, detect_header_row, to_text as _cell_to_text


DEFAULT_TEMPLATE_FILENAME = "Class_Define_Template.xlsx"

# (Item_Code, Catalog_Item_Name, Description_Prefix, Group)
# Catalog_Item_Name → Piping_Material_Class_Data 의 Item_Name 열
# Description_Prefix → Item_Description 조합 시 선두 토큰(PIPE, NIPPLE, ELBOW …)
ITEM_CODE_DB_HEADERS = [
    "Item_Code",
    "Catalog_Item_Name",
    "Description_Prefix",
    "Group",
]
ITEM_CODE_DB_DEFAULT_ROWS = [
    ("P", "PIPE", "PIPE", "Pipe_Group"),
    ("JN", "NIPPLE (PE/TE) 75mm", "NIPPLE", "Pipe_Group"),
    ("JNP", "NIPPLE (PBE) 75mm", "NIPPLE", "Pipe_Group"),
    ("JN1", "NIPPLE (PE/TE) 100mm", "NIPPLE", "Pipe_Group"),
    ("JNP1", "NIPPLE (PBE) 100mm", "NIPPLE", "Pipe_Group"),
    ("JNT", "NIPPLE (TBE) 75mm", "NIPPLE", "Pipe_Group"),
    ("JNT1", "NIPPLE (TBE) 100mm", "NIPPLE", "Pipe_Group"),
    ("RC", "REDUCER CON", "REDUCER CON", "Fitting_Group"),
    ("RE", "REDUCER ECC", "REDUCER ECC", "Fitting_Group"),
    ("RCS", "SWAGE CON", "SWAGE CON", "Fitting_Group"),
    ("RES", "SWAGE ECC", "SWAGE ECC", "Fitting_Group"),
    ("E", "ELBOW 90 DEG LR", "ELBOW 90 DEG LR", "Fitting_Group"),
    ("ES", "ELBOW 90 DEG SR", "ELBOW 90 DEG SR", "Fitting_Group"),
    ("E4", "ELBOW 45 DEG LR", "ELBOW 45 DEG LR", "Fitting_Group"),
    ("ES4", "ELBOW 45 DEG SR", "ELBOW 45 DEG SR", "Fitting_Group"),
    ("PL", "PLUG", "PLUG", "Fitting_Group"),
    ("F", "FLANGE", "FLANGE", "Flange_Group"),
    ("G", "GASKET", "GASKET", "Gasket_Group"),
    ("B", "BOLT&NUT", "BOLT", "Bolt_Group"),
]

def _class_and_fluid_sheet_headers() -> tuple[list[str], list[str]]:
    merged = config.config_manager.merged()
    dt, dp = read_design_units_from_merged(merged)
    return class_define_headers(dt, dp), fluid_service_headers(dt, dp)


JOINT_HEADERS = [
    "Class_Name",
    "Size_From",
    "Size_To",
    "Pipe_Joint_Type",
    "Maintenance_Joint_Type",
    "Remarks",
]

SCHEDULE_HEADERS = [
    "Class_Name",
    "Size_From",
    "Size_To",
    "Schedule",
]

REDUCING_TABLE_HEADERS = ["Table_Code", "Size1", "Size2", "Item_Type", "Remarks"]
BRANCH_TABLE_HEADERS = REDUCING_TABLE_HEADERS
REDUCING_TABLE_SIZE_PAIRS: tuple[tuple[str, str], ...] = (
    ("0.75", "0.5"),
    ("0.75", "0.375"),
    ("1", "0.75"),
    ("1", "0.5"),
    ("1.25", "1"),
    ("1.25", "0.75"),
    ("1.25", "0.5"),
    ("1.5", "1.25"),
    ("1.5", "1"),
    ("1.5", "0.75"),
    ("1.5", "0.5"),
    ("2", "1.5"),
    ("2", "1.25"),
    ("2", "1"),
    ("2", "0.75"),
    ("2.5", "2"),
    ("2.5", "1.5"),
    ("2.5", "1.25"),
    ("2.5", "1"),
    ("3", "2.5"),
    ("3", "2"),
    ("3", "1.5"),
    ("3", "1.25"),
    ("3.5", "3"),
    ("3.5", "2.5"),
    ("3.5", "2"),
    ("3.5", "1.5"),
    ("3.5", "1.25"),
    ("4", "3.5"),
    ("4", "3"),
    ("4", "2.5"),
    ("4", "2"),
    ("4", "1.5"),
    ("5", "4"),
    ("5", "3.5"),
    ("5", "3"),
    ("5", "2.5"),
    ("5", "2"),
    ("6", "5"),
    ("6", "4"),
    ("6", "3.5"),
    ("6", "3"),
    ("6", "2.5"),
    ("8", "6"),
    ("8", "5"),
    ("8", "4"),
    ("8", "3.5"),
    ("10", "8"),
    ("10", "6"),
    ("10", "5"),
    ("10", "4"),
    ("12", "10"),
    ("12", "8"),
    ("12", "6"),
    ("12", "5"),
    ("14", "12"),
    ("14", "10"),
    ("14", "8"),
    ("14", "6"),
    ("16", "14"),
    ("16", "12"),
    ("16", "10"),
    ("16", "8"),
    ("18", "16"),
    ("18", "14"),
    ("18", "12"),
    ("18", "10"),
    ("20", "18"),
    ("20", "16"),
    ("20", "14"),
    ("20", "12"),
    ("22", "20"),
    ("22", "18"),
    ("22", "16"),
    ("22", "14"),
    ("24", "22"),
    ("24", "20"),
    ("24", "18"),
    ("24", "16"),
    ("26", "24"),
    ("26", "22"),
    ("26", "20"),
    ("26", "18"),
    ("28", "26"),
    ("28", "24"),
    ("28", "20"),
    ("28", "18"),
    ("30", "28"),
    ("30", "26"),
    ("30", "24"),
    ("30", "20"),
    ("32", "30"),
    ("32", "28"),
    ("32", "26"),
    ("32", "24"),
    ("34", "32"),
    ("34", "30"),
    ("34", "26"),
    ("34", "24"),
    ("36", "34"),
    ("36", "32"),
    ("36", "30"),
    ("36", "26"),
    ("36", "24"),
    ("38", "36"),
    ("38", "34"),
    ("38", "32"),
    ("38", "30"),
    ("38", "28"),
    ("38", "26"),
    ("40", "38"),
    ("40", "36"),
    ("40", "34"),
    ("40", "32"),
    ("40", "30"),
    ("42", "40"),
    ("42", "38"),
    ("42", "36"),
    ("42", "34"),
    ("42", "32"),
    ("42", "30"),
    ("44", "42"),
    ("44", "40"),
    ("44", "38"),
    ("44", "36"),
    ("46", "44"),
    ("46", "42"),
    ("46", "40"),
    ("46", "38"),
    ("48", "46"),
    ("48", "44"),
    ("48", "42"),
    ("48", "40"),
)

# 템플릿 Branch/Reducing 선입력 시 제외: NPS 24 초과, 비표준 분수 0.375·1.25·2.5·3.5
TEMPLATE_SIZE_MAX_NPS = 24.0
TEMPLATE_SIZE_EXCLUDED_NUMBERS: frozenset[float] = frozenset({0.375, 1.25, 2.5, 3.5})
# Reducing 표: Main Size(Size1) 최소값 (size_matrix_editor / _cell_allowed 와 동일)
MIN_REDUCING_SIZE1_NPS = 0.75

PIPE_HEADERS = [
    "Class_Name",
    "Item_Code",
    "Size_From",
    "Size_To",
    "Mat_Code",
    "Mat_Class",
    "Manufacturing_Method",
    "End_Type_1",
    "End_Type_2",
    "Length",
    "Remarks",
]

FITTING_HEADERS = [
    "Class_Name",
    "Item_Code",
    "Size_From",
    "Size_To",
    "Mat_Code",
    "Mat_Class",
    "Manufacturing_Method",
    "Rating",
    "End_Type_1",
    "End_Type_2",
    "Remarks",
]

FLANGE_HEADERS = [
    "Class_Name",
    "Item_Code",
    "Size1_From",
    "Size1_To",
    "Size2_From",
    "Size2_To",
    "Mat_Code",
    "Mat_Class",
    "Rating",
    "Facing",
    "Flange_Type",
    "Remarks",
]

GASKET_HEADERS = [
    "Class_Name",
    "Item_Code",
    "Size_From",
    "Size_To",
    "Gasket_Type",
    "Material_Primary",
    "Material_Secondary",
    "Material_Inner_Ring",
    "Material_Outer_Ring",
    "Rating",
    "Facing",
    "Thickness",
    "Remarks",
]

BOLT_HEADERS = [
    "Class_Name",
    "Item_Code",
    "Size_From",
    "Size_To",
    "Bolt_Type",
    "Bolt_Mat_Code",
    "Bolt_Mat_Class",
    "Nut_Type",
    "Nut_Mat_Code",
    "Nut_Mat_Class",
    "Bolt_Length_Table",
    "Remarks",
]

VALVE_HEADERS = [
    "Class_Name",
    "Item_Code",
    "Valve_Type",
    "Size1_From",
    "Size1_To",
    "Size2_From",
    "Size2_To",
    "Body_Mat",
    "Stem/Disc/Ball_Mat",
    "Seat_Mat",
    "Rating",
    "End_Type",
    "Bonnet_Type",
    "Operation",
    "Disc_Type",
    "Remarks",
]

HEADER_FONT = Font(bold=True)
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
FREEZE_PANES = "A2"


def _get_logger() -> logging.Logger:
    # Keep module self-contained; if project has a logger module, prefer it.
    try:
        from logger import get_logger  # type: ignore

        return get_logger()
    except Exception:
        logger = logging.getLogger("template_generator")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(levelname)s: %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger


def _project_root() -> Path:
    return config.program_root()


def _col_letter(col_index_1_based: int) -> str:
    result = ""
    x = col_index_1_based
    while x > 0:
        x, rem = divmod(x - 1, 26)
        result = chr(ord("A") + rem) + result
    return result


def _set_headers_and_widths(ws, headers: list[str]) -> None:
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT
        ws.column_dimensions[_col_letter(col_idx)].width = min(
            40, max(12, len(header) + 2)
        )

    ws.freeze_panes = FREEZE_PANES


def _size_number(size_text: str) -> float:
    return float(size_text.strip())


def _nominal_size_selected_is_dn() -> bool:
    raw = str(config.config_manager.get("units_notation.nominal_size.selected", "") or "").strip().upper()
    return raw == "DN"


def _sorted_nominal_labels_for_prefill() -> list[str]:
    """NPS 또는 DN 목록(프로젝트 nps_master)을 숫자 순으로."""
    if _nominal_size_selected_is_dn():
        lst = config.config_manager.get("nps_master.dn_list", []) or []
    else:
        lst = config.config_manager.get("nps_master.nps_list", []) or []
    raw = [str(x).strip() for x in lst if str(x).strip()]
    return sorted(raw, key=_size_number)


def _branch_pairs_from_sorted_sizes(sizes: list[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for s1 in sizes:
        for s2 in sizes:
            if _size_number(s1) >= _size_number(s2):
                out.append((s1, s2))
    return _sorted_size_pairs(out)


def _reducing_pairs_from_sorted_sizes(sizes: list[str]) -> list[tuple[str, str]]:
    """dn_list / nps_list 기준: Size1 > Size2 이고 Size1 이 최소 인치와 동일 규칙(MIN_REDUCING_SIZE1_NPS)."""
    out: list[tuple[str, str]] = []
    for s1 in sizes:
        n1 = _size_number(s1)
        if n1 < MIN_REDUCING_SIZE1_NPS:
            continue
        for s2 in sizes:
            if _size_number(s2) < n1:
                out.append((s1, s2))
    return _sorted_size_pairs(out)


def _prefill_reducing_pairs() -> list[tuple[str, str]]:
    if _nominal_size_selected_is_dn():
        return _reducing_pairs_from_sorted_sizes(_sorted_nominal_labels_for_prefill())
    return _template_reducing_pairs_filtered()


def _template_size_allowed(size_text: str) -> bool:
    n = _size_number(size_text)
    if n > TEMPLATE_SIZE_MAX_NPS:
        return False
    if n in TEMPLATE_SIZE_EXCLUDED_NUMBERS:
        return False
    return True


def _sorted_size_pairs(
    pairs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    return sorted(pairs, key=lambda p: (_size_number(p[0]), _size_number(p[1])))


def _template_reducing_pairs_filtered() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for a, b in REDUCING_TABLE_SIZE_PAIRS:
        if _template_size_allowed(a) and _template_size_allowed(b):
            pairs.append((a, b))
    return _sorted_size_pairs(pairs)


def _build_branch_table_size_pairs() -> list[tuple[str, str]]:
    if _nominal_size_selected_is_dn():
        return _branch_pairs_from_sorted_sizes(_sorted_nominal_labels_for_prefill())
    filtered = _template_reducing_pairs_filtered()
    sizes_set: set[str] = set()
    for a, b in filtered:
        sizes_set.add(a)
        sizes_set.add(b)
    sizes = sorted(sizes_set, key=_size_number)
    out: list[tuple[str, str]] = []
    for size1 in sizes:
        for size2 in sizes:
            if _size_number(size1) >= _size_number(size2):
                out.append((size1, size2))
    return _sorted_size_pairs(out)


def _prefill_size_pairs(ws, size_pairs: list[tuple[str, str]]) -> None:
    # Table_Code/Item_Type/Remarks 는 사용자 입력 대상으로 비워 둡니다.
    for row_idx, (size1, size2) in enumerate(size_pairs, start=2):
        ws.cell(row=row_idx, column=2, value=size1)  # Size1
        ws.cell(row=row_idx, column=3, value=size2)  # Size2


def _ensure_json_file(path: Path, default_obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(default_obj, f, indent=2, ensure_ascii=False)


def ensure_program_json_sidecars() -> None:
    """data/ 아래 JSON 보조 파일이 없으면 기본 내용으로 생성합니다(기존 파일은 유지)."""
    _ensure_json_file(config.class_material_mapping_path(), DEFAULT_CLASS_MATERIAL_MAPPING)
    _ensure_json_file(config.component_mapping_path(), DEFAULT_COMPONENT_MAPPING)


def _detect_item_code_db_header_row(ws) -> int:
    for req in (["Item_Code", "Group"], ["Item_Code", "Item_Name"]):
        try:
            return detect_header_row(ws, req)
        except ValueError:
            continue
    raise ValueError("Item_Code_DB header row not found")


def _rewrite_item_code_db_to_standard_layout(ws) -> None:
    """헤더·데이터를 ITEM_CODE_DB_HEADERS 순서로 재배치(업그레이드·정렬용)."""
    try:
        hr = _detect_item_code_db_header_row(ws)
    except ValueError:
        return
    htc = build_header_index(ws, hr)
    if "Item_Code" not in htc:
        return
    rows_out: list[list[object]] = []
    for r in range(hr + 1, ws.max_row + 1):
        code = _cell_to_text(ws.cell(row=r, column=htc["Item_Code"]).value)
        if not code:
            continue
        cat = ""
        if "Catalog_Item_Name" in htc:
            cat = _cell_to_text(ws.cell(row=r, column=htc["Catalog_Item_Name"]).value)
        elif "Item_Name" in htc:
            cat = _cell_to_text(ws.cell(row=r, column=htc["Item_Name"]).value)
        prefix = ""
        if "Description_Prefix" in htc:
            prefix = _cell_to_text(ws.cell(row=r, column=htc["Description_Prefix"]).value)
        if not prefix and cat:
            prefix = cat
        grp = _cell_to_text(ws.cell(row=r, column=htc["Group"]).value) if "Group" in htc else ""
        rows_out.append([code, cat, prefix, grp])
    if ws.max_row:
        ws.delete_rows(1, ws.max_row)
    for col_idx, header in enumerate(ITEM_CODE_DB_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT
        ws.column_dimensions[_col_letter(col_idx)].width = min(
            40, max(12, len(header) + 2)
        )
    ws.freeze_panes = "A2"
    for row_idx, row in enumerate(rows_out, start=2):
        for col_idx, value in enumerate(row, start=1):
            ws.cell(row=row_idx, column=col_idx, value=value)


def ensure_item_code_db() -> Path:
    """
    data/Item_Code_DB.xlsx 가 없으면 기본 행으로 생성합니다.
    레거시(Item_Name 단일 열)면 Catalog_Item_Name / Description_Prefix 형태로 맞춥니다.
    `ITEM_CODE_DB_DEFAULT_ROWS` 에만 있는 Item_Code 행을 헤더 이름 기준으로 추가합니다.
    """
    logger = _get_logger()
    d = config.data_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = config.item_code_db_path()
    if path.exists():
        try:
            wb = load_workbook(path)
            if "Item_Code_DB" not in wb.sheetnames:
                return path
            ws = wb["Item_Code_DB"]
            modified = False
            try:
                hr = _detect_item_code_db_header_row(ws)
                htc = build_header_index(ws, hr)
            except ValueError:
                logger.warning("Item_Code_DB: could not detect headers; skipping merge")
                return path

            if not all(h in htc for h in ITEM_CODE_DB_HEADERS):
                _rewrite_item_code_db_to_standard_layout(ws)
                modified = True
                header_row = 1
            else:
                header_row = hr

            htc = build_header_index(ws, header_row)

            col_code = htc.get("Item_Code", 1)
            codes_seen: set[str] = set()
            for r in range(2, ws.max_row + 1):
                v = ws.cell(row=r, column=col_code).value
                if v is not None and str(v).strip():
                    codes_seen.add(str(v).strip().upper())
            next_row = ws.max_row + 1
            for row in ITEM_CODE_DB_DEFAULT_ROWS:
                code = str(row[0]).strip().upper()
                if code and code not in codes_seen:
                    for hi, header in enumerate(ITEM_CODE_DB_HEADERS):
                        ws.cell(
                            row=next_row,
                            column=htc[header],
                            value=row[hi],
                        )
                    codes_seen.add(code)
                    next_row += 1
                    modified = True
            if modified:
                wb.save(path)
                logger.info(f"Updated Item_Code DB: {path}")
        except Exception as exc:
            logger.warning(f"Could not merge default Item_Code rows: {exc}")
        return path

    wb = Workbook()
    ws = wb.active
    ws.title = "Item_Code_DB"
    for col_idx, header in enumerate(ITEM_CODE_DB_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT
        ws.column_dimensions[_col_letter(col_idx)].width = min(
            40, max(12, len(header) + 2)
        )
    ws.freeze_panes = "A2"
    for row_idx, row in enumerate(ITEM_CODE_DB_DEFAULT_ROWS, start=2):
        for col_idx, value in enumerate(row, start=1):
            ws.cell(row=row_idx, column=col_idx, value=value)
    wb.save(path)
    logger.info(f"Created Item_Code_DB: {path}")
    return path


def ensure_all_program_data_files() -> None:
    """템플릿·PMS 공통: JSON 사이드카 + Item_Code DB 보장."""
    ensure_program_json_sidecars()
    ensure_item_code_db()


def _write_dict_rows(
    ws,
    headers: list[str],
    rows: list[dict[str, str]],
) -> None:
    for row_idx, row in enumerate(rows, start=2):
        for col_idx, header in enumerate(headers, start=1):
            ws.cell(row=row_idx, column=col_idx, value=row.get(header, ""))


def _write_named_size_tables(ws, tables: list[NamedSizeTable]) -> None:
    """Reducing_Table / Branch_Table: 각 행에 Table_Code를 반복 기록."""
    row_idx = 2
    for tbl in tables:
        code = tbl.table_code.strip()
        for sr in tbl.rows:
            ws.cell(row=row_idx, column=1, value=code)
            ws.cell(row=row_idx, column=2, value=sr.size1)
            ws.cell(row=row_idx, column=3, value=sr.size2)
            ws.cell(row=row_idx, column=4, value=sr.item_type)
            ws.cell(row=row_idx, column=5, value=sr.remarks)
            row_idx += 1


def _append_component_group_sheets(wb: Workbook) -> None:
    ws_pipe = wb.create_sheet(title="Pipe_Group")
    _set_headers_and_widths(ws_pipe, PIPE_HEADERS)

    ws_fitting = wb.create_sheet(title="Fitting_Group")
    _set_headers_and_widths(ws_fitting, FITTING_HEADERS)

    ws_flange = wb.create_sheet(title="Flange_Group")
    _set_headers_and_widths(ws_flange, FLANGE_HEADERS)

    ws_gasket = wb.create_sheet(title="Gasket_Group")
    _set_headers_and_widths(ws_gasket, GASKET_HEADERS)

    ws_bolt = wb.create_sheet(title="Bolt_Group")
    _set_headers_and_widths(ws_bolt, BOLT_HEADERS)

    ws_valve = wb.create_sheet(title="Valve_Group")
    _set_headers_and_widths(ws_valve, VALVE_HEADERS)


def generate_class_define_template(
    output_path: Optional[Path | str] = None,
    class_level: Optional[ClassLevelBundle] = None,
) -> Path:
    """
    Create `Class_Define_Template.xlsx` with required sheets:
    - Class_Define
    - Fluid_Service
    - Joint
    - Schedule
    - Reducing_Table
    - Branch_Table
    - Pipe_Group
    - Fitting_Group
    - Flange_Group
    - Gasket_Group
    - Bolt_Group
    - Valve_Group

    동시에 data/Item_Code_DB.xlsx 가 없으면 생성합니다(기존 파일은 유지).

    class_level:
        GUI에서 수집한 클래스 수준 데이터. 지정 시 Class_Define·Fluid_Service·Joint·Schedule·
        Branch_Table·Reducing_Table 내용을 이 값으로 채웁니다. None 이면 기존처럼
        Branch/Reducing 시트만 표준 사이즈 쌍으로 선입력합니다.
    """
    logger = _get_logger()

    template_path = (
        Path(output_path)
        if output_path is not None
        else _project_root() / DEFAULT_TEMPLATE_FILENAME
    )

    wb = Workbook()

    class_headers, fluid_headers = _class_and_fluid_sheet_headers()

    ws_define = wb.active
    ws_define.title = "Class_Define"
    _set_headers_and_widths(ws_define, class_headers)

    ws_fluid = wb.create_sheet(title="Fluid_Service")
    _set_headers_and_widths(ws_fluid, fluid_headers)

    ws_joint = wb.create_sheet(title="Joint")
    _set_headers_and_widths(ws_joint, JOINT_HEADERS)

    ws_schedule = wb.create_sheet(title="Schedule")
    _set_headers_and_widths(ws_schedule, SCHEDULE_HEADERS)

    ws_branch_table = wb.create_sheet(title="Branch_Table")
    _set_headers_and_widths(ws_branch_table, BRANCH_TABLE_HEADERS)

    ws_reducing_table = wb.create_sheet(title="Reducing_Table")
    _set_headers_and_widths(ws_reducing_table, REDUCING_TABLE_HEADERS)

    if class_level is None:
        _prefill_size_pairs(ws_branch_table, _build_branch_table_size_pairs())
        _prefill_size_pairs(ws_reducing_table, _prefill_reducing_pairs())
    else:
        _write_dict_rows(ws_define, class_headers, class_level.class_define_rows)
        _write_dict_rows(ws_fluid, fluid_headers, class_level.fluid_service_rows)
        _write_dict_rows(ws_joint, JOINT_HEADERS, class_level.joint_rows)
        _write_dict_rows(ws_schedule, SCHEDULE_HEADERS, class_level.schedule_rows)
        _write_named_size_tables(ws_branch_table, class_level.branch_tables)
        _write_named_size_tables(ws_reducing_table, class_level.reducing_tables)

    _append_component_group_sheets(wb)

    try:
        wb.save(template_path)
    except PermissionError as e:
        raise PermissionError(
            f"엑셀 파일이 열려있어서 저장에 실패했습니다. "
            f"해당 파일을 닫고 다시 시도해 주세요. (path: {template_path})"
        ) from e

    ensure_all_program_data_files()

    logger.info(f"Generated template: {template_path}")
    return template_path


if __name__ == "__main__":
    generate_class_define_template()

