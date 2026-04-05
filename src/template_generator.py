from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font

import config
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
    ("F", "FLANGE", "FLANGE", "Flange_Group"),
]

CLASS_DEFINE_HEADERS = [
    "Revision_No",
    "Class_Name",
    "Design_Code",
    "Class_Base_Material",
    "Class_Rating",
    "Corrosion_Allowance",
    "Design_Temperature_From",
    "Design_Temperature_To",
    "Design_Pressure_From",
    "Design_Pressure_To",
    "Fluid_Service",
    "Branch_Table_1",
    "Branch_Table_2",
    "Reducing_Table_1",
    "Reducing_Table_2",
    "Global_Special_Req",
    "Remarks",
]

FLUID_SERVICE_HEADERS = [
    "Class_Name",
    "Fluid_Service_Code",
    "Fluid_Service_Name",
    "Min_Design_Temperature",
    "Max_Design_Temperature",
    "Min_Design_Pressure",
    "Max_Design_Pressure",
    "NDE",
    "PWHT",
]

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
    "Dim_Standard",
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
    "Dim_Standard",
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
    "End_Type",
    "Dim_Standard",
    "Remarks",
]

VALVE_HEADERS = [
    "Class_Name",
    "Item_Code",
    "Valve_Type",
    "Size_From",
    "Size_To",
    "Body_Mat",
    "Trim_Mat",
    "Rating",
    "End_Type",
    "Operation",
    "Bonnet_Type",
    "Valve_Feature",
    "Dim_Standard",
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
        ws.cell(row=1, column=col_idx, value=header).font = HEADER_FONT
        ws.cell(row=1, column=col_idx).alignment = HEADER_ALIGNMENT
        # Auto width based on header length.
        ws.column_dimensions[_col_letter(col_idx)].width = min(
            40, max(12, len(header) + 2)
        )

    ws.freeze_panes = FREEZE_PANES


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
        ws.cell(row=1, column=col_idx, value=header).font = HEADER_FONT
        ws.cell(row=1, column=col_idx).alignment = HEADER_ALIGNMENT
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


def generate_class_define_template(
    output_path: Optional[Path | str] = None,
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
    - Flange
    - Valve

    동시에 data/Item_Code_DB.xlsx 가 없으면 생성합니다(기존 파일은 유지).
    """
    logger = _get_logger()

    template_path = (
        Path(output_path)
        if output_path is not None
        else _project_root() / DEFAULT_TEMPLATE_FILENAME
    )

    wb = Workbook()

    ws_define = wb.active
    ws_define.title = "Class_Define"
    _set_headers_and_widths(ws_define, CLASS_DEFINE_HEADERS)

    ws_fluid = wb.create_sheet(title="Fluid_Service")
    _set_headers_and_widths(ws_fluid, FLUID_SERVICE_HEADERS)

    ws_joint = wb.create_sheet(title="Joint")
    _set_headers_and_widths(ws_joint, JOINT_HEADERS)

    ws_schedule = wb.create_sheet(title="Schedule")
    _set_headers_and_widths(ws_schedule, SCHEDULE_HEADERS)

    ws_reducing_table = wb.create_sheet(title="Reducing_Table")
    _set_headers_and_widths(ws_reducing_table, REDUCING_TABLE_HEADERS)

    ws_branch_table = wb.create_sheet(title="Branch_Table")
    _set_headers_and_widths(ws_branch_table, BRANCH_TABLE_HEADERS)

    ws_pipe = wb.create_sheet(title="Pipe_Group")
    _set_headers_and_widths(ws_pipe, PIPE_HEADERS)

    ws_fitting = wb.create_sheet(title="Fitting_Group")
    _set_headers_and_widths(ws_fitting, FITTING_HEADERS)

    ws_flange = wb.create_sheet(title="Flange")
    _set_headers_and_widths(ws_flange, FLANGE_HEADERS)

    ws_valve = wb.create_sheet(title="Valve")
    _set_headers_and_widths(ws_valve, VALVE_HEADERS)

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

