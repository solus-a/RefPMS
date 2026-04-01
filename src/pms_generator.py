from __future__ import annotations

from pathlib import Path
import logging
from typing import Optional

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

import config


OUTPUT_FILENAME = "Piping_Material_Class_Data.xlsx"
OUTPUT_SHEET_NAME = "Piping_Material_Class_Data"

NPS_LIST = [
    "0.5",
    "0.75",
    "1",
    "1.5",
    "2",
    "3",
    "4",
    "6",
    "8",
    "10",
    "12",
    "14",
    "16",
    "18",
    "20",
    "22",
    "24",
]

OUTPUT_COLUMNS = [
    "Class_Name",
    "Item_Code",
    "Size1",
    "Size2",
    "Thickness1",
    "Thickness2",
    "Commodity_Code",
    "Item_Description",
    "Item_Name",
    "Remarks",
]

ITEM_CODE_OUTPUT_ORDER = [
    "P",
    "JN",
    "JNP",
    "JN1",
    "JNP1",
    "E",
    "ES",
    "E4",
    "ES4",
    "RC",
    "RE",
    "RCS",
    "RES",
]

def _autofit_output_sheet_columns(
    ws,
    column_count: int,
    min_width: float = 12.0,
    max_width: float = 55.0,
) -> None:
    """헤더·데이터 셀 문자열 길이에 맞춰 열 너비를 조정합니다."""
    last_row = max(ws.max_row, 1)
    for col in range(1, column_count + 1):
        max_len = 0
        for row in range(1, last_row + 1):
            val = ws.cell(row=row, column=col).value
            if val is None:
                continue
            cell_len = len(str(val).strip())
            if cell_len > max_len:
                max_len = cell_len
        width = min(max_width, max(min_width, max_len + 2))
        ws.column_dimensions[get_column_letter(col)].width = width


SCHEDULE_REQUIRED_HEADERS = [
    "Class_Name",
    "Size_From",
    "Size_To",
    "Schedule",
]

REDUCING_TABLE_REQUIRED_HEADERS = [
    "Table_Code",
    "Size1",
    "Size2",
    "Item_Type",
]

MATERIAL_SHEET_CONFIGS = [
    {
        "sheet_name": "Pipe_Group",
        "required_headers": [
            "Class_Name",
            "Item_Code",
            "Size_From",
            "Size_To",
        ],
        "size_from_1": "Size_From",
        "size_to_1": "Size_To",
        "size_from_2": None,
        "size_to_2": None,
    },
    {
        "sheet_name": "Fitting_Group",
        "required_headers": [
            "Class_Name",
            "Item_Code",
            "Size1_From",
            "Size1_To",
        ],
        "size_from_1": "Size1_From",
        "size_to_1": "Size1_To",
        "size_from_2": "Size2_From",
        "size_to_2": "Size2_To",
    },
    {
        "sheet_name": "Flange",
        "required_headers": [
            "Class_Name",
            "Item_Code",
            "Size1_From",
            "Size1_To",
        ],
        "size_from_1": "Size1_From",
        "size_to_1": "Size1_To",
        "size_from_2": "Size2_From",
        "size_to_2": "Size2_To",
    },
    {
        "sheet_name": "Valve",
        "required_headers": [
            "Class_Name",
            "Item_Code",
            "Size_From",
            "Size_To",
        ],
        "size_from_1": "Size_From",
        "size_to_1": "Size_To",
        "size_from_2": None,
        "size_to_2": None,
    },
]


def _get_logger() -> logging.Logger:
    try:
        from logger import get_logger  # type: ignore

        return get_logger()
    except Exception:
        logger = logging.getLogger("pms_generator")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(levelname)s: %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger


def _to_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_float(text_value: str) -> Optional[float]:
    if not text_value:
        return None
    try:
        return float(text_value)
    except ValueError:
        return None


def _item_code_priority(item_code: str) -> int:
    code = _to_text(item_code)
    try:
        return ITEM_CODE_OUTPUT_ORDER.index(code)
    except ValueError:
        return len(ITEM_CODE_OUTPUT_ORDER)


def _explode_size_range(size_from: str, size_to: str) -> list[str]:
    from_num = _to_float(size_from)
    to_num = _to_float(size_to)
    if from_num is None or to_num is None:
        return []

    nps_index_by_float = {float(nps): idx for idx, nps in enumerate(NPS_LIST)}
    from_idx = nps_index_by_float.get(from_num)
    to_idx = nps_index_by_float.get(to_num)
    if from_idx is None or to_idx is None:
        return []
    if from_idx > to_idx:
        return []

    return NPS_LIST[from_idx : to_idx + 1]


def _detect_header_row(ws, expected_headers: list[str], max_scan_rows: int = 10) -> int:
    for row_idx in range(1, max_scan_rows + 1):
        row_values = [ws.cell(row=row_idx, column=c).value for c in range(1, ws.max_column + 1)]
        header_set = {_to_text(v) for v in row_values if _to_text(v)}
        if all(h in header_set for h in expected_headers):
            return row_idx
    raise ValueError(
        f"Could not detect header row in sheet '{ws.title}'. "
        f"Expected headers: {', '.join(expected_headers)}"
    )


def _build_header_index(ws, header_row: int) -> dict[str, int]:
    header_to_col: dict[str, int] = {}
    for col in range(1, ws.max_column + 1):
        header = _to_text(ws.cell(row=header_row, column=col).value)
        if header:
            header_to_col[header] = col
    return header_to_col


def _get_cell_text(ws, row_idx: int, header_to_col: dict[str, int], header_name: Optional[str]) -> str:
    if not header_name:
        return ""
    col = header_to_col.get(header_name)
    if not col:
        return ""
    return _to_text(ws.cell(row=row_idx, column=col).value)


def _pick_first_non_empty(
    ws,
    row_idx: int,
    header_to_col: dict[str, int],
    candidates: list[str],
) -> str:
    for name in candidates:
        value = _get_cell_text(ws, row_idx, header_to_col, name)
        if value:
            return value
    return ""


def _join_tokens(*tokens: str) -> str:
    cleaned = [t.strip() for t in tokens if t and t.strip()]
    return " ".join(cleaned)


def _mat_code_grade(
    ws,
    row_idx: int,
    header_to_col: dict[str, int],
    mat_code_header: str = "Mat_Code",
) -> str:
    mat_code = _get_cell_text(ws, row_idx, header_to_col, mat_code_header)
    mat_grade = _pick_first_non_empty(
        ws,
        row_idx,
        header_to_col,
        ["Mat_Grade", "Material_Code_Grade", "Mat_Class"],
    )
    if mat_code and mat_grade:
        return f"{mat_code}-{mat_grade}"
    return mat_code or mat_grade


def _format_size2(size_from: str, size_to: str) -> str:
    a = _to_text(size_from)
    b = _to_text(size_to)
    if not a and not b:
        return ""
    if not b or a == b:
        return a
    return f"{a}-{b}"


def _load_schedule_rows(workbook) -> list[dict[str, str]]:
    if "Schedule" not in workbook.sheetnames:
        return []

    ws = workbook["Schedule"]
    try:
        header_row = _detect_header_row(ws, SCHEDULE_REQUIRED_HEADERS)
    except ValueError:
        return []

    header_to_col = _build_header_index(ws, header_row)
    missing = [h for h in SCHEDULE_REQUIRED_HEADERS if h not in header_to_col]
    if missing:
        return []

    rows: list[dict[str, str]] = []
    for row_idx in range(header_row + 1, ws.max_row + 1):
        class_name = _get_cell_text(ws, row_idx, header_to_col, "Class_Name")
        if not class_name:
            continue
        rows.append(
            {
                "Class_Name": class_name,
                "Size_From": _get_cell_text(ws, row_idx, header_to_col, "Size_From"),
                "Size_To": _get_cell_text(ws, row_idx, header_to_col, "Size_To"),
                "Schedule": _get_cell_text(ws, row_idx, header_to_col, "Schedule"),
            }
        )
    return rows


def _load_item_code_db(logger: logging.Logger) -> dict[str, dict[str, str]]:
    """
    data/Item_Code_DB.xlsx → {Item_Code: {Item_Name, Group}}
    파일이 없으면 빈 dict, 경고 로그만 남깁니다.
    """
    path = config.item_code_db_path()
    if not path.exists():
        logger.warning(f"Item_Code DB not found (continuing without DB): {path}")
        return {}

    try:
        wb = load_workbook(path, data_only=True)
    except Exception as exc:
        logger.warning(f"Could not load Item_Code DB (continuing): {path} — {exc}")
        return {}

    if "Item_Code_DB" not in wb.sheetnames:
        logger.warning("Item_Code_DB sheet missing in Item_Code DB workbook")
        return {}

    ws = wb["Item_Code_DB"]
    required = ["Item_Code", "Item_Name", "Group"]
    try:
        header_row = _detect_header_row(ws, required)
    except ValueError:
        logger.warning("Could not detect Item_Code_DB header row")
        return {}

    header_to_col = _build_header_index(ws, header_row)
    out: dict[str, dict[str, str]] = {}
    for row_idx in range(header_row + 1, ws.max_row + 1):
        code = _get_cell_text(ws, row_idx, header_to_col, "Item_Code")
        if not code:
            continue
        out[code] = {
            "Item_Name": _get_cell_text(ws, row_idx, header_to_col, "Item_Name"),
            "Group": _get_cell_text(ws, row_idx, header_to_col, "Group"),
        }
    return out


def _load_reducing_table(workbook) -> dict[str, dict[tuple[str, str], str]]:
    """
    Reducing_Table 시트 로드.
    Table_Code가 빈칸이면 직전 값으로 forward fill 하여 item_type 매핑을 구성합니다.
    reducing_data[table_code][(size1, size2)] = item_type
    """
    if "Reducing_Table" not in workbook.sheetnames:
        return {}

    ws = workbook["Reducing_Table"]
    try:
        header_row = _detect_header_row(ws, REDUCING_TABLE_REQUIRED_HEADERS)
    except ValueError:
        return {}

    header_to_col = _build_header_index(ws, header_row)
    missing = [h for h in REDUCING_TABLE_REQUIRED_HEADERS if h not in header_to_col]
    if missing:
        return {}

    reducing_data: dict[str, dict[tuple[str, str], str]] = {}
    previous_table_code = ""
    for row_idx in range(header_row + 1, ws.max_row + 1):
        table_code_raw = _get_cell_text(ws, row_idx, header_to_col, "Table_Code")
        if table_code_raw:
            previous_table_code = table_code_raw
        table_code = previous_table_code

        size1 = _get_cell_text(ws, row_idx, header_to_col, "Size1")
        size2 = _get_cell_text(ws, row_idx, header_to_col, "Size2")
        item_type = _get_cell_text(ws, row_idx, header_to_col, "Item_Type").upper()
        if not table_code or not size1 or not size2 or not item_type:
            continue

        if table_code not in reducing_data:
            reducing_data[table_code] = {}
        reducing_data[table_code][(size1, size2)] = item_type

    return reducing_data


def _load_class_reducing_table_codes(workbook) -> dict[str, str]:
    """
    Class_Define 시트에서 Class_Name -> Reducing_Table_1 코드 매핑을 읽습니다.
    """
    if "Class_Define" not in workbook.sheetnames:
        return {}

    ws = workbook["Class_Define"]
    required = ["Class_Name", "Reducing_Table_1"]
    try:
        header_row = _detect_header_row(ws, required)
    except ValueError:
        return {}

    header_to_col = _build_header_index(ws, header_row)
    class_to_table: dict[str, str] = {}
    for row_idx in range(header_row + 1, ws.max_row + 1):
        class_name = _get_cell_text(ws, row_idx, header_to_col, "Class_Name")
        table_code = _get_cell_text(ws, row_idx, header_to_col, "Reducing_Table_1")
        if class_name and table_code:
            class_to_table[class_name] = table_code
    return class_to_table


def _lookup_schedule_thickness(
    schedule_rows: list[dict[str, str]],
    class_name: str,
    size_nps: str,
) -> str:
    if not size_nps or not class_name:
        return ""

    for row in schedule_rows:
        if row["Class_Name"] != class_name:
            continue
        exploded = _explode_size_range(row["Size_From"], row["Size_To"])
        if exploded and size_nps in exploded:
            return row["Schedule"]
        # 단일 사이즈만 적힌 행 (To 비어 있음)
        if not row["Size_To"] and row["Size_From"] and size_nps == row["Size_From"]:
            return row["Schedule"]

    return ""


def _build_item_description_by_rule(
    sheet_name: str,
    ws,
    row_idx: int,
    header_to_col: dict[str, int],
    item_code: str,
    item_name: str,
    thickness1: str,
    thickness2: str,
    db_group: Optional[str] = None,
) -> str:
    method = _pick_first_non_empty(
        ws, row_idx, header_to_col, ["Manufacturing_Method", "Method"]
    )
    dim_standard = _get_cell_text(ws, row_idx, header_to_col, "Dim_Standard")
    row_fallback_thickness = _pick_first_non_empty(
        ws, row_idx, header_to_col, ["Rating_Thickness", "Schedule", "Rating"]
    )
    sch1 = thickness1 or row_fallback_thickness

    if sheet_name == "Pipe_Group":
        mat = _mat_code_grade(ws, row_idx, header_to_col, "Mat_Code")
        end_type_1 = _pick_first_non_empty(
            ws, row_idx, header_to_col, ["End_Type_1", "End_Type"]
        )
        remarks = _get_cell_text(ws, row_idx, header_to_col, "Remarks")
        pipe_label = item_name or "PIPE"
        return _join_tokens(
            pipe_label,
            mat,
            method,
            end_type_1,
            sch1,
            remarks,
            dim_standard,
        )

    if sheet_name == "Fitting_Group":
        if db_group and db_group.strip() != "Fitting_Group":
            return ""
        mat = _mat_code_grade(ws, row_idx, header_to_col, "Mat_Code")
        end_type_1 = _get_cell_text(ws, row_idx, header_to_col, "End_Type_1")
        end_type_2 = _get_cell_text(ws, row_idx, header_to_col, "End_Type_2")
        end_type_upper = end_type_1.strip().upper()
        fitting_thickness_or_rating = sch1
        if end_type_upper == "SW":
            sw_rating = _get_cell_text(ws, row_idx, header_to_col, "Rating")
            if sw_rating.strip().upper().startswith("CL"):
                converted = sw_rating.strip()[2:].strip()
                fitting_thickness_or_rating = f"{converted}#" if converted else ""
            else:
                fitting_thickness_or_rating = sw_rating

        reducer_codes = {"RC", "RE", "RCS", "RES"}
        if item_code in reducer_codes:
            rating_raw = _get_cell_text(ws, row_idx, header_to_col, "Rating").strip()
            rating_token = rating_raw
            if rating_raw.upper().startswith("CL"):
                converted = rating_raw[2:].strip()
                rating_token = f"{converted}#" if converted else ""

            def _is_schedule_end(end_type: str) -> bool:
                t = end_type.strip().upper()
                if not t:
                    return True
                return any(key in t for key in ["BW", "PBE", "BLE", "TSE"])

            def _side_token(end_type: str, schedule_token: str) -> str:
                t = end_type.strip().upper()
                if "SW" in t:
                    return rating_token
                if _is_schedule_end(t):
                    return schedule_token
                return schedule_token

            side1 = _side_token(end_type_1, sch1)
            side2 = _side_token(end_type_2 or end_type_1, thickness2 or sch1)
            thickness_pair = side1
            if side2:
                thickness_pair = f"{side1} x {side2}" if side1 else side2

            end_type_token = end_type_1
            if end_type_2 and end_type_2 != end_type_1:
                end_type_token = f"{end_type_1}/{end_type_2}"

            return _join_tokens(item_name, mat, method, end_type_token, thickness_pair)

        remarks = _get_cell_text(ws, row_idx, header_to_col, "Remarks")
        tokens = [
            item_name,
            mat,
            method,
            end_type_1,
            fitting_thickness_or_rating,
            dim_standard,
        ]
        if remarks:
            tokens.append(remarks)
        return _join_tokens(*tokens)

    if sheet_name == "Flange":
        end_type = _get_cell_text(ws, row_idx, header_to_col, "End_Type")
        facing = _get_cell_text(ws, row_idx, header_to_col, "Facing")
        mat = _mat_code_grade(ws, row_idx, header_to_col, "Mat_Code")
        rating = _pick_first_non_empty(ws, row_idx, header_to_col, ["Rating", "Rating_Thickness"])
        bore_schedule = _get_cell_text(ws, row_idx, header_to_col, "Bore_Schedule")
        show_sch = end_type.upper() == "WN" or bool(bore_schedule)
        bore_token = bore_schedule if end_type.upper() == "WN" and bool(bore_schedule) else ""
        sch_from_table = sch1 if show_sch else ""
        thickness_part = bore_token or sch_from_table
        return _join_tokens(item_name, end_type, facing, mat, rating, thickness_part, dim_standard)

    if sheet_name == "Valve":
        body_mat = _get_cell_text(ws, row_idx, header_to_col, "Body_Mat")
        trim_mat = _get_cell_text(ws, row_idx, header_to_col, "Trim_Mat")
        rating = _pick_first_non_empty(ws, row_idx, header_to_col, ["Rating", "Rating_Thickness"])
        end_type = _get_cell_text(ws, row_idx, header_to_col, "End_Type")
        operation = _get_cell_text(ws, row_idx, header_to_col, "Operation")
        bonnet_type = _get_cell_text(ws, row_idx, header_to_col, "Bonnet_Type")
        valve_feature = _get_cell_text(ws, row_idx, header_to_col, "Valve_Feature")
        trim_segment = f"/ TRIM {trim_mat}" if trim_mat else ""
        return _join_tokens(
            item_name,
            body_mat,
            trim_segment,
            rating,
            end_type,
            operation,
            bonnet_type,
            valve_feature,
            sch1,
            dim_standard,
        )

    return ""


def _iter_output_rows(
    workbook,
    schedule_rows: list[dict[str, str]],
    reducing_data: dict[str, dict[tuple[str, str], str]],
    class_reducing_codes: dict[str, str],
    item_code_db: dict[str, dict[str, str]],
    logger: logging.Logger,
):
    fitting_template_rows: dict[tuple[str, str], int] = {}
    fitting_ws = workbook["Fitting_Group"] if "Fitting_Group" in workbook.sheetnames else None
    fitting_header_to_col: dict[str, int] = {}
    if fitting_ws is not None:
        try:
            fitting_header_row = _detect_header_row(
                fitting_ws, ["Class_Name", "Item_Code", "End_Type_1"]
            )
            fitting_header_to_col = _build_header_index(fitting_ws, fitting_header_row)
            for row_idx in range(fitting_header_row + 1, fitting_ws.max_row + 1):
                cls = _get_cell_text(fitting_ws, row_idx, fitting_header_to_col, "Class_Name")
                code = _get_cell_text(fitting_ws, row_idx, fitting_header_to_col, "Item_Code")
                if cls and code:
                    fitting_template_rows[(cls, code)] = row_idx
        except ValueError:
            fitting_ws = None

    for sheet_config in MATERIAL_SHEET_CONFIGS:
        sheet_name = sheet_config["sheet_name"]
        if sheet_name not in workbook.sheetnames:
            continue

        ws = workbook[sheet_name]
        required_headers = sheet_config["required_headers"]
        header_row = _detect_header_row(ws, required_headers)
        header_to_col = _build_header_index(ws, header_row)

        missing = [h for h in required_headers if h not in header_to_col]
        if missing:
            raise ValueError(f"Missing expected column(s) in {sheet_name}: {', '.join(missing)}")

        for row_idx in range(header_row + 1, ws.max_row + 1):
            class_name = _get_cell_text(ws, row_idx, header_to_col, "Class_Name")
            item_code = _get_cell_text(ws, row_idx, header_to_col, "Item_Code")
            if not class_name and not item_code:
                continue
            if not class_name:
                continue

            db_row: Optional[dict[str, str]] = None
            if item_code:
                db_row = item_code_db.get(item_code)
                if not db_row:
                    logger.warning(
                        f"Item_Code not in DB (Item_Name left empty): {item_code!r}"
                    )

            item_name = db_row["Item_Name"] if db_row else ""
            db_group = db_row.get("Group") if db_row else None

            desc_item_name = item_name
            if sheet_name == "Valve" and not desc_item_name:
                desc_item_name = _get_cell_text(ws, row_idx, header_to_col, "Valve_Type")

            size_from_1 = _get_cell_text(ws, row_idx, header_to_col, sheet_config["size_from_1"])
            size_to_1 = _get_cell_text(ws, row_idx, header_to_col, sheet_config["size_to_1"])
            size2_display = _format_size2(
                _get_cell_text(ws, row_idx, header_to_col, sheet_config["size_from_2"]),
                _get_cell_text(ws, row_idx, header_to_col, sheet_config["size_to_2"]),
            )

            remarks = _get_cell_text(ws, row_idx, header_to_col, "Remarks")

            exploded_sizes = _explode_size_range(size_from_1, size_to_1)
            if not exploded_sizes:
                size1_out = size_from_1 or size_to_1
                th1 = _lookup_schedule_thickness(schedule_rows, class_name, size1_out)
                th2 = ""
                if size2_display:
                    if "-" not in size2_display:
                        th2 = _lookup_schedule_thickness(schedule_rows, class_name, size2_display)
                    else:
                        part = size2_display.split("-", 1)[0].strip()
                        th2 = _lookup_schedule_thickness(schedule_rows, class_name, part)

                desc = _build_item_description_by_rule(
                    sheet_name,
                    ws,
                    row_idx,
                    header_to_col,
                    item_code,
                    desc_item_name,
                    th1,
                    th2,
                    db_group=db_group,
                )
                yield {
                    "Class_Name": class_name,
                    "Item_Code": item_code,
                    "Size1": size1_out,
                    "Size2": size2_display,
                    "Thickness1": th1,
                    "Thickness2": th2,
                    "Commodity_Code": "",
                    "Item_Description": desc,
                    "Item_Name": item_name,
                    "Remarks": remarks,
                }
                continue

            for exploded_size in exploded_sizes:
                th1 = _lookup_schedule_thickness(schedule_rows, class_name, exploded_size)
                th2 = ""
                if size2_display:
                    if "-" not in size2_display:
                        th2 = _lookup_schedule_thickness(schedule_rows, class_name, size2_display)
                    else:
                        part = size2_display.split("-", 1)[0].strip()
                        th2 = _lookup_schedule_thickness(schedule_rows, class_name, part)

                desc = _build_item_description_by_rule(
                    sheet_name,
                    ws,
                    row_idx,
                    header_to_col,
                    item_code,
                    desc_item_name,
                    th1,
                    th2,
                    db_group=db_group,
                )
                yield {
                    "Class_Name": class_name,
                    "Item_Code": item_code,
                    "Size1": exploded_size,
                    "Size2": size2_display,
                    "Thickness1": th1,
                    "Thickness2": th2,
                    "Commodity_Code": "",
                    "Item_Description": desc,
                    "Item_Name": item_name,
                    "Remarks": remarks,
                }

    # Reducing_Table 기반 추가 생성 (RD/SN -> RC/RE/RCS/RES 분해)
    if fitting_ws is None or not reducing_data:
        return

    for class_name, table_code in class_reducing_codes.items():
        size_map = reducing_data.get(table_code, {})
        if not size_map:
            continue

        for (size1, size2), item_type in size_map.items():
            item_type_upper = item_type.upper()
            mapped_codes: list[str] = []
            if item_type_upper == "RD":
                mapped_codes = ["RC", "RE"]
            elif item_type_upper == "SN":
                mapped_codes = ["RCS", "RES"]
            else:
                continue

            for mapped_code in mapped_codes:
                template_row_idx = fitting_template_rows.get((class_name, mapped_code))
                if template_row_idx is None:
                    logger.warning(
                        f"Fitting_Group template row missing for class/item: {class_name}/{mapped_code}"
                    )
                    continue

                db_row = item_code_db.get(mapped_code, {})
                item_name = _to_text(db_row.get("Item_Name", ""))
                db_group = _to_text(db_row.get("Group", ""))
                th1 = _lookup_schedule_thickness(schedule_rows, class_name, size1)
                th2 = _lookup_schedule_thickness(schedule_rows, class_name, size2)
                desc = _build_item_description_by_rule(
                    "Fitting_Group",
                    fitting_ws,
                    template_row_idx,
                    fitting_header_to_col,
                    mapped_code,
                    item_name,
                    th1,
                    th2,
                    db_group=db_group,
                )

                yield {
                    "Class_Name": class_name,
                    "Item_Code": mapped_code,
                    "Size1": size1,
                    "Size2": size2,
                    "Thickness1": th1,
                    "Thickness2": th2,
                    "Commodity_Code": "",
                    "Item_Description": desc,
                    "Item_Name": item_name,
                    "Remarks": "",
                }


def generate_piping_material_class_data(
    template_path: str | Path,
    output_path: Optional[str | Path] = None,
    output_sheet_name: str = OUTPUT_SHEET_NAME,
) -> Path:
    logger = _get_logger()

    template_path = Path(template_path)
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    if output_path is None:
        output_path = template_path.parent / OUTPUT_FILENAME
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    item_code_db = _load_item_code_db(logger)

    in_wb = load_workbook(template_path, data_only=True)
    schedule_rows = _load_schedule_rows(in_wb)
    reducing_data = _load_reducing_table(in_wb)
    class_reducing_codes = _load_class_reducing_table_codes(in_wb)

    out_wb = Workbook()
    out_ws = out_wb.active
    out_ws.title = output_sheet_name

    for col_idx, name in enumerate(OUTPUT_COLUMNS, start=1):
        out_ws.cell(row=1, column=col_idx, value=name)

    out_row = 2
    rows = list(
        _iter_output_rows(
        in_wb,
        schedule_rows,
        reducing_data,
        class_reducing_codes,
        item_code_db,
        logger,
        )
    )
    rows.sort(
        key=lambda r: (
            _to_text(r.get("Class_Name")),
            _item_code_priority(_to_text(r.get("Item_Code"))),
            _to_float(_to_text(r.get("Size1"))) if _to_float(_to_text(r.get("Size1"))) is not None else 10**9,
            _to_text(r.get("Size1")),
            _to_text(r.get("Size2")),
        )
    )

    for row_values in rows:
        for col_idx, column_name in enumerate(OUTPUT_COLUMNS, start=1):
            out_ws.cell(row=out_row, column=col_idx, value=row_values.get(column_name, ""))
        out_row += 1

    _autofit_output_sheet_columns(out_ws, len(OUTPUT_COLUMNS))

    try:
        out_wb.save(output_path)
    except PermissionError as e:
        raise PermissionError(
            f"엑셀 파일이 열려있어서 저장에 실패했습니다. "
            f"해당 파일을 닫고 다시 시도해 주세요. (path: {output_path})"
        ) from e

    logger.info(f"Generated Piping_Material_Class_Data: {output_path}")
    return output_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("Usage: py pms_generator.py <template_path>")

    generate_piping_material_class_data(sys.argv[1])
