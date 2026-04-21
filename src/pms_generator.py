from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

import config
from class_spec import (
    ClassSpec,
    corrosion_allowance_validation_messages,
    load_class_specs_from_workbook,
    log_class_constraint_warnings,
)
from excel_sheet_utils import (
    build_header_index as _build_header_index,
    detect_header_row as _detect_header_row,
    get_cell_text as _get_cell_text,
    pick_first_non_empty as _pick_first_non_empty,
    to_float as _to_float,
    to_text as _to_text,
)
from thickness_engine import (
    explode_size_range as _explode_size_range,
    load_schedule_rows,
    lookup_schedule_thickness,
)
from validator import (
    load_class_size_ranges,
    load_component_mapping,
    validate_size_range_for_row,
    validate_template_row,
)

# 프로젝트 설정 로드
cfg = config.config_manager

OUTPUT_FILENAME = cfg.get("output_settings.filename", "Piping_Material_Class_Data.xlsx")
OUTPUT_SHEET_NAME = cfg.get("output_settings.sheet_name", "Piping_Material_Class_Data")
OUTPUT_COLUMNS = cfg.get("output_settings.columns", [])
ITEM_CODE_OUTPUT_ORDER = cfg.get("output_settings.item_order", [])


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


REDUCING_TABLE_REQUIRED_HEADERS = [
    "Table_Code",
    "Size1",
    "Size2",
    "Item_Type",
]

# RC/RE/RCS/RES는 Reducing_Table에서만 풀고, Fitting_Group 템플릿 행으로는 중복 생성하지 않음.
REDUCER_ITEM_CODES_FROM_TABLE = frozenset({"RC", "RE", "RCS", "RES"})
# T/RT/TH는 클래스에 Branch_Table_1 이 연결되고 해당 테이블에 행이 있으면 Branch_Table에서만 전개.
# TH(Half Coupling)는 Branch_Table에 존재해야 하며, 실제 전개는 Size2(분기관) 기준으로만 처리.
BRANCH_ITEM_CODES_FROM_TABLE = frozenset({"T", "RT", "TH"})
BRANCH_TABLE_REQUIRED_HEADERS = [
    "Table_Code",
    "Size1",
    "Size2",
    "Item_Type",
]
VALVE_SHEET_NAMES = frozenset({"Valve", "Valve_Group"})

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
            "Size_From",
            "Size_To",
        ],
        "size_from_1": "Size_From",
        "size_to_1": "Size_To",
        "size_from_2": None,
        "size_to_2": None,
    },
    {
        "sheet_name": "Flange_Group",
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
        "sheet_name": "Gasket_Group",
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
        "sheet_name": "Valve_Group",
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
    {
        "sheet_name": "Bolt_Group",
        "required_headers": [
            "Class_Name",
            "Item_Code",
            "Size_From",
            "Size_To",
            "Bolt_Type",
            "Bolt_Mat_Code",
            "Nut_Type",
            "Nut_Mat_Code",
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


def _item_code_priority(item_code: str) -> int:
    code = _to_text(item_code)
    try:
        return ITEM_CODE_OUTPUT_ORDER.index(code)
    except ValueError:
        return len(ITEM_CODE_OUTPUT_ORDER)


def _join_tokens(*tokens: str) -> str:
    cleaned = [t.strip() for t in tokens if t and t.strip()]
    return " ".join(cleaned)


def _is_valve_sheet(sheet_name: str) -> bool:
    return sheet_name in VALVE_SHEET_NAMES


def _get_cell_text_any(ws, row_idx: int, header_to_col: dict[str, int], fields: list[str]) -> str:
    for field in fields:
        value = _get_cell_text(ws, row_idx, header_to_col, field)
        if value:
            return value
    return ""


# B16.9 BW 엘보는 설명에 LR/SR 유지. 소켓·나사 단조(전형적으로 ASME B16.11 치수)는 LR/SR 생략.
# B16.11 적용은 Fitting_Group 의 Dim_Standard 컬럼이 아니라 프로젝트 설계코드(B31.3/B31.4) + End_Type 으로 전제.
# 발주 Item_Name 은 엘보 코드(E/ES/E4/ES4) 전부에서 LR/SR 접미사 제거.
ELBOW_LR_SR_ITEM_CODES = frozenset({"E", "ES", "E4", "ES4"})


def _strip_trailing_lr_sr(label: str) -> str:
    """문자열 끝의 ' LR' / ' SR' 토큰 제거(대소문자 무시)."""
    return re.sub(r"\s+\b(LR|SR)\s*$", "", _to_text(label), flags=re.I).strip()


def _rating_looks_forged_socket_class(rating_raw: str) -> bool:
    """ASME B16.11 단조 이음관 등급(CL2000/3000/6000/9000 등). 플랜지 CL150~2500 과 구분."""
    r = _to_text(rating_raw).upper().replace(" ", "")
    if not r:
        return False
    return bool(re.match(r"^CL(2000|3000|6000|9000)\b", r))


def _piping_design_implies_socket_screwed_b16_11_fitting_dims(class_design_code: str) -> bool:
    """
    해당 Class 의 Design_Code 가 소켓·나사 단조이음관 치수에 ASME B16.11 계열을 전제로 할 때
    (예: ASME B31.3 / B31.4). 컴포넌트 시트의 Dim_Standard 대신 End_Type 으로 구분.
    """
    sel = _to_text(class_design_code).upper()
    return "B31.3" in sel or "B31.4" in sel


def _class_design_code_for(class_specs: dict[str, ClassSpec], class_name: str) -> str:
    spec = class_specs.get(class_name)
    if not spec:
        return ""
    return _to_text(spec.get("design_code", ""))


def _class_nominal_mode_for(class_specs: dict[str, ClassSpec], class_name: str) -> str:
    """Class_Define.Nominal_Size_System 값. 미지정 시 빈 문자열 (카탈로그는 NPS 로 폴백)."""
    spec = class_specs.get(class_name)
    if not spec:
        return ""
    return _to_text(spec.get("nominal_size_system", ""))


def _fitting_elbow_should_strip_lr_sr(
    item_code: str, dim_standard: str, end_type_1: str, rating: str
) -> bool:
    """
    When True, also strip LR/SR from Description_Prefix (Fitting_Group elbows). Reserved; currently always off.
    """
    _ = (item_code, dim_standard, end_type_1, rating)
    return False


def _reducer_description_dim_standard(dim_standard: str) -> str:
    """
    RC/RE/RCS/RES 설명 끝에 붙일 규격 문자열.
    Dim_Standard에는 이음(BW/PE 등)을 넣지 않고 규격명만 적는다(예: ASME B16.9, MSS SP-95).
    예전 템플릿에 `ASME B16.9 BW`처럼 잘못 붙어 있으면 설명 끝 중복을 막기 위해 `ASME B16.9`로만 정규화.
    """
    s = _to_text(dim_standard)
    if not s:
        return ""
    if re.match(r"^ASME\s+B16\.9\s+BW\s*$", s, flags=re.I):
        return "ASME B16.9"
    return s


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


NIPPLE_PIPE_CODES = frozenset({"JN", "JN1", "JNP", "JNP1", "JNT", "JNT1"})


def _apply_length_to_catalog_nipple_name(catalog: str, length_val: str) -> str:
    """Swap trailing NNmm suffix in catalog name for Length; append length if no mm suffix."""
    c = _to_text(catalog)
    lv = _to_text(length_val)
    if not c:
        return lv
    if not lv:
        return c
    stripped = c.strip()
    if re.search(r"(?i)\d+\s*mm\s*$", stripped):
        replaced = re.sub(r"(?i)\d+\s*mm\s*$", lv.strip(), stripped)
        return replaced.strip()
    return f"{stripped} {lv.strip()}".strip()


def _try_nipple_pipe_output(
    item_code: str,
    ws,
    row_idx: int,
    header_to_col: dict[str, int],
    th1: str,
    catalog_item_name: str,
    description_prefix: str,
) -> Optional[tuple[str, str, str]]:
    """
    Pipe_Group 니플: Item_Description 선두는 Item_Code_DB 의 Description_Prefix.
    길이는 Length 열만 사용(Remarks 에서 길이 폴백 없음). 특수 조건은 Remarks 를 설명·출력에 반영.
    Item_Name 은 Catalog_Item_Name 을 기준으로 길이 열을 반영해 정리합니다.
    """
    code = _to_text(item_code).upper()
    if code not in NIPPLE_PIPE_CODES:
        return None
    mat = _mat_code_grade(ws, row_idx, header_to_col, "Mat_Code")
    method = _pick_first_non_empty(
        ws, row_idx, header_to_col, ["Manufacturing_Method", "Method"]
    )
    dim_standard = _get_cell_text(ws, row_idx, header_to_col, "Dim_Standard")
    length_note = _get_cell_text(ws, row_idx, header_to_col, "Length")
    remarks = _get_cell_text(ws, row_idx, header_to_col, "Remarks")
    et1 = _get_cell_text(ws, row_idx, header_to_col, "End_Type_1")
    et2 = _get_cell_text(ws, row_idx, header_to_col, "End_Type_2")
    sch = th1 or _pick_first_non_empty(
        ws, row_idx, header_to_col, ["Rating_Thickness", "Schedule", "Rating"]
    )
    prefix = _to_text(description_prefix) or "NIPPLE"
    if code in ("JN", "JN1"):
        pair = f"{et1}/{et2}".strip("/") if et2 else et1
        desc = _join_tokens(prefix, mat, method, pair, sch, length_note, remarks, dim_standard)
        out_name = _apply_length_to_catalog_nipple_name(catalog_item_name, length_note)
        if not out_name:
            out_name = f"{prefix} ({pair}) {length_note}".strip()
        return desc, out_name, remarks
    if code in ("JNP", "JNP1"):
        desc = _join_tokens(prefix, mat, method, "PBE", sch, length_note, remarks, dim_standard)
        out_name = _apply_length_to_catalog_nipple_name(catalog_item_name, length_note)
        if not out_name:
            out_name = f"{prefix} (PBE) {length_note}".strip()
        return desc, out_name, remarks
    # JNT / JNT1: 양끝 나사(TE/TE) → TBE
    desc = _join_tokens(
        prefix,
        mat,
        method,
        "TBE",
        sch,
        length_note,
        remarks,
        dim_standard,
    )
    out_name = _apply_length_to_catalog_nipple_name(catalog_item_name, length_note)
    if not out_name:
        out_name = f"{prefix} (TBE) {length_note}".strip()
    return desc, out_name, remarks


def _normalize_reducer_end_kind(raw: str) -> str:
    """
    RCS/RES 이음 표기용. BE(비벨/버트)·PE(플레인)·TE(나사) 계열로 정규화.
    매핑 불가 시 빈 문자열 → 호출부에서 원문 조합으로 폴백.
    """
    t = _to_text(raw).upper().replace(" ", "")
    if not t:
        return ""
    if t in ("BE", "BW", "BWE") or (t.startswith("BW") and "WN" not in t):
        return "BE"
    if t == "PE":
        return "PE"
    if any(x in t for x in ("TE", "NPT", "TSE")):
        return "TE"
    return ""


def _reducer_both_ends_token(kind: str) -> str:
    if kind == "BE":
        return "BBE"
    if kind == "PE":
        return "PBE"
    if kind == "TE":
        return "TBE"
    return ""


def _reducer_large_small_token(kind: str, large_or_small: str) -> str:
    """large_or_small: 'L' 또는 'S'. BE/PE만 정의(TE·기타는 빈 문자열)."""
    if kind == "BE":
        return "BLE" if large_or_small == "L" else "BSE"
    if kind == "PE":
        return "PLE" if large_or_small == "L" else "PSE"
    return ""


def _rcs_res_end_type_token(
    et1_raw: str,
    et2_raw: str,
    size1: Optional[str],
    size2: Optional[str],
) -> str:
    """
    RCS·RES: L/S = Large/Small 단면, B = Both(양끝 동일 타입 → BBE·PBE·TBE).
    Size1/End_Type_1, Size2/End_Type_2는 Reducing_Table·템플릿 열 순서에 대응.
    """
    e1 = _to_text(et1_raw)
    e2 = _to_text(et2_raw)
    k1 = _normalize_reducer_end_kind(e1)
    k2 = _normalize_reducer_end_kind(e2)
    if not k1 or not k2:
        if e1 and e2 and e1.upper() != e2.upper():
            return f"{e1}/{e2}"
        return e1 or e2

    if k1 == k2:
        both = _reducer_both_ends_token(k1)
        return both if both else (e1 or e2)

    n1 = _to_float(_to_text(size1))
    n2 = _to_float(_to_text(size2))
    if n1 is None or n2 is None or n1 == n2:
        return f"{e1}/{e2}" if e1 and e2 else (e1 or e2)

    if n1 > n2:
        large_k, small_k = k1, k2
        large_raw, small_raw = e1, e2
    else:
        large_k, small_k = k2, k1
        large_raw, small_raw = e2, e1

    if large_k in ("BE", "PE") and small_k in ("BE", "PE"):
        tl = _reducer_large_small_token(large_k, "L")
        ts = _reducer_large_small_token(small_k, "S")
        if tl and ts:
            return f"{tl}/{ts}"

    return f"{large_raw}/{small_raw}"


def _flange_rating_display(rating: str) -> str:
    """CL150 → 150# 등 플랜지 발주 표기. 그 외는 원문 유지."""
    raw = _to_text(rating)
    if raw.upper().startswith("CL"):
        tail = _to_text(raw[2:])
        return f"{tail}#" if tail else raw
    return raw


def _normalize_flange_type_token(raw_flange_type: str) -> str:
    """
    Flange 타입 표기 정규화.
    운영 기준:
    - Flange_Type 입력은 약어 중심(SW/WN/THRD/SO/LJ)
    - Blind/Reducing은 Item_Code(FB/FR)로 별도 구분
    """
    text = _to_text(raw_flange_type).strip()
    upper = text.upper()
    if not upper:
        return ""
    # 레거시 문자열 매핑은 하지 않는다.
    # 운영 약어(SW/WN/THRD/SO/LJ)를 템플릿에 그대로 입력해 사용한다.
    # BL/RTJ/RSO 등은 현재 운영 입력 대상이 아니며, FB/FR은 Item_Code로 관리한다.
    return upper


def _gasket_material_token(gasket_type: str, mat_primary: str, mat_secondary: str) -> str:
    gt = _to_text(gasket_type).strip().upper()
    p = _to_text(mat_primary).strip()
    s = _to_text(mat_secondary).strip()
    if not p and not s:
        return ""
    if not s:
        return p
    if gt in {"SPIRAL WOUND", "ENVELOPED", "JACKETED"}:
        return f"{p}+{s}" if p else s
    return _join_tokens(p, s)


def _bolt_dim_standard_token(bolt_dim_standard: str, nut_dim_standard: str) -> str:
    b = _to_text(bolt_dim_standard).strip()
    n = _to_text(nut_dim_standard).strip()
    if not b and not n:
        return ""
    if not n:
        return b
    n_upper = n.upper()
    if n_upper.startswith("ASME "):
        n = n[5:].strip()
    return f"{b} / {n}".strip()


def _normalize_gasket_thickness(gasket_type: str, thickness: str) -> str:
    raw = _to_text(thickness).strip()
    # 가스켓 두께는 템플릿 입력값을 그대로 출력한다.
    return raw


def _load_item_code_db(logger: logging.Logger) -> dict[str, dict[str, str]]:
    """
    data/Item_Code_DB.xlsx → {Item_Code: {Item_Name, Description_Prefix, Group}}
    - Item_Name: Catalog_Item_Name(없으면 레거시 Item_Name) → PMS 출력 Item_Name 기준
    - Description_Prefix: 설명 문자열 선두(없으면 카탈로그명과 동일)
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
    header_row: Optional[int] = None
    for req in (["Item_Code", "Group"], ["Item_Code", "Item_Name"]):
        try:
            header_row = _detect_header_row(ws, req)
            break
        except ValueError:
            continue
    if header_row is None:
        logger.warning("Could not detect Item_Code_DB header row")
        return {}

    header_to_col = _build_header_index(ws, header_row)
    out: dict[str, dict[str, str]] = {}
    for row_idx in range(header_row + 1, ws.max_row + 1):
        code = _get_cell_text(ws, row_idx, header_to_col, "Item_Code")
        if not code:
            continue
        catalog = _get_cell_text(ws, row_idx, header_to_col, "Catalog_Item_Name")
        if not catalog:
            catalog = _get_cell_text(ws, row_idx, header_to_col, "Item_Name")
        prefix = _get_cell_text(ws, row_idx, header_to_col, "Description_Prefix")
        if not prefix:
            prefix = catalog
        group = _get_cell_text(ws, row_idx, header_to_col, "Group")
        out[code] = {
            "Item_Name": catalog,
            "Description_Prefix": prefix,
            "Group": group,
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


def _load_branch_table(workbook) -> dict[str, dict[tuple[str, str], str]]:
    """
    Branch_Table 시트: Reducing_Table 과 동일 헤더(Table_Code, Size1, Size2, Item_Type).
    branch_data[table_code][(size1, size2)] = item_type  (T, RT, …)
    """
    if "Branch_Table" not in workbook.sheetnames:
        return {}

    ws = workbook["Branch_Table"]
    try:
        header_row = _detect_header_row(ws, BRANCH_TABLE_REQUIRED_HEADERS)
    except ValueError:
        return {}

    header_to_col = _build_header_index(ws, header_row)
    missing = [h for h in BRANCH_TABLE_REQUIRED_HEADERS if h not in header_to_col]
    if missing:
        return {}

    branch_data: dict[str, dict[tuple[str, str], str]] = {}
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

        if table_code not in branch_data:
            branch_data[table_code] = {}
        branch_data[table_code][(size1, size2)] = item_type

    return branch_data


def _load_class_branch_table_codes(workbook) -> dict[str, str]:
    """Class_Define: Class_Name -> Branch_Table_1 코드."""
    if "Class_Define" not in workbook.sheetnames:
        return {}

    ws = workbook["Class_Define"]
    required = ["Class_Name", "Branch_Table_1"]
    try:
        header_row = _detect_header_row(ws, required)
    except ValueError:
        return {}

    header_to_col = _build_header_index(ws, header_row)
    out: dict[str, str] = {}
    for row_idx in range(header_row + 1, ws.max_row + 1):
        class_name = _get_cell_text(ws, row_idx, header_to_col, "Class_Name")
        table_code = _get_cell_text(ws, row_idx, header_to_col, "Branch_Table_1")
        if class_name and table_code:
            out[class_name] = table_code
    return out


def _branch_rt_template_reference_nps(
    run_nps: str,
) -> str:
    """
    이경 티(RT) 템플릿 행 선택 기준은 RUN(size1)이다.
    """
    return _to_text(run_nps)


def _find_fitting_template_row_for_nps(
    fitting_ws,
    fitting_header_row: int,
    fitting_header_to_col: dict[str, int],
    class_name: str,
    item_code: str,
    reference_nps: str,
    logger: logging.Logger,
    nominal_mode: str,
    *,
    log_if_missing: bool = True,
) -> Optional[int]:
    """Size_From~Size_To 구간에 reference_nps 가 포함되는 첫 Fitting_Group 템플릿 행."""
    ref = _to_text(reference_nps)
    if not ref:
        return None
    ref_span = _explode_size_range(ref, ref, nominal_mode)
    ref_set = set(ref_span) if ref_span else {ref}

    for row_idx in range(fitting_header_row + 1, fitting_ws.max_row + 1):
        cls = _get_cell_text(fitting_ws, row_idx, fitting_header_to_col, "Class_Name")
        code = _get_cell_text(fitting_ws, row_idx, fitting_header_to_col, "Item_Code")
        if cls != class_name or code != item_code:
            continue
        sf = _get_cell_text(fitting_ws, row_idx, fitting_header_to_col, "Size_From")
        st = _get_cell_text(fitting_ws, row_idx, fitting_header_to_col, "Size_To")
        span = _explode_size_range(sf, st, nominal_mode)
        span_set = set(span) if span else set()
        if ref_set & span_set:
            return row_idx

    if log_if_missing:
        logger.warning(
            f"No Fitting_Group template row for {class_name}/{item_code} covering NPS {ref!r}"
        )
    return None


def _find_rt_fitting_template_row(
    fitting_ws,
    fitting_header_row: int,
    fitting_header_to_col: dict[str, int],
    class_name: str,
    run_nps: str,
    branch_nps: str,
    logger: logging.Logger,
    nominal_mode: str,
) -> Optional[int]:
    """
    이경 티(RT): 소단이 SW 구간(예: 0.5~1.5)이어도 대단이 2\" 이상 BW 구간이면 BW 템플릿을 쓴다.
    """
    ref = _branch_rt_template_reference_nps(run_nps)
    row_sw = _find_fitting_template_row_for_nps(
        fitting_ws,
        fitting_header_row,
        fitting_header_to_col,
        class_name,
        "RT",
        ref,
        logger,
        nominal_mode,
        log_if_missing=False,
    )
    if row_sw is None:
        return _find_fitting_template_row_for_nps(
            fitting_ws,
            fitting_header_row,
            fitting_header_to_col,
            class_name,
            "RT",
            run_nps,
            logger,
            nominal_mode,
        )

    et_ref = _get_cell_text(fitting_ws, row_sw, fitting_header_to_col, "End_Type_1")
    f_run = _to_float(_to_text(run_nps))
    if "SW" in et_ref.upper() and f_run is not None and f_run >= 2:
        row_bw = _find_fitting_template_row_for_nps(
            fitting_ws,
            fitting_header_row,
            fitting_header_to_col,
            class_name,
            "RT",
            run_nps,
            logger,
            nominal_mode,
            log_if_missing=False,
        )
        if row_bw is not None:
            et_run = _get_cell_text(fitting_ws, row_bw, fitting_header_to_col, "End_Type_1")
            if "BW" in et_run.upper():
                return row_bw

    if row_sw is not None:
        return row_sw
    return _find_fitting_template_row_for_nps(
        fitting_ws,
        fitting_header_row,
        fitting_header_to_col,
        class_name,
        "RT",
        run_nps,
        logger,
        nominal_mode,
    )


def _build_item_description_by_rule(
    sheet_name: str,
    ws,
    row_idx: int,
    header_to_col: dict[str, int],
    item_code: str,
    description_lead: str,
    thickness1: str,
    thickness2: str,
    db_group: Optional[str] = None,
    reducer_size1: Optional[str] = None,
    reducer_size2: Optional[str] = None,
    fitting_dual_schedule: bool = False,
    size1_value: Optional[str] = None,
    class_design_code: str = "",
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
        pipe_label = description_lead or "PIPE"
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
        is_plug_item = item_code.upper() == "PL"
        dim_has_b16_11 = "B16.11" in dim_standard.upper()
        implicit_socket_dims = _piping_design_implies_socket_screwed_b16_11_fitting_dims(
            class_design_code
        )
        rating_cell = _get_cell_text(ws, row_idx, header_to_col, "Rating")
        forged_socket_rating = _rating_looks_forged_socket_class(rating_cell)
        fitting_thickness_or_rating = sch1
        if is_plug_item:
            # ASME B16.11 PLUG는 class/rating으로 식별하지 않으므로 설명 토큰에서 두께·등급을 생략.
            fitting_thickness_or_rating = ""
        if end_type_upper == "SW" or (
            end_type_upper in {"TE", "NPT", "PT"}
            and not is_plug_item
            and (implicit_socket_dims or dim_has_b16_11 or forged_socket_rating)
        ):
            sw_rating = rating_cell
            if sw_rating.strip().upper().startswith("CL"):
                converted = sw_rating.strip()[2:].strip()
                fitting_thickness_or_rating = f"{converted}#" if converted else ""
            else:
                fitting_thickness_or_rating = sw_rating

        if fitting_dual_schedule and item_code in ("T", "RT"):
            rating_raw = _get_cell_text(ws, row_idx, header_to_col, "Rating").strip()
            rating_token = rating_raw
            if rating_raw.upper().startswith("CL"):
                converted = rating_raw[2:].strip()
                rating_token = f"{converted}#" if converted else ""

            def _tee_is_schedule_end(end_type: str) -> bool:
                t = end_type.strip().upper()
                if not t:
                    return True
                return any(key in t for key in ["BW", "PBE", "BLE", "TSE"])

            def _tee_side_token(end_type: str, schedule_token: str) -> str:
                t = end_type.strip().upper()
                if "SW" in t:
                    return rating_token
                if _tee_is_schedule_end(t):
                    return schedule_token
                return schedule_token

            sch2_eff = thickness2 or sch1
            side1 = _tee_side_token(end_type_1, sch1)
            side2 = _tee_side_token(end_type_2 or end_type_1, sch2_eff)
            if side1 and side2 and side1 == side2:
                thickness_pair = side1
            elif side1 and side2:
                thickness_pair = f"{side1} x {side2}"
            else:
                thickness_pair = side1 or side2

            end_token = end_type_1
            if end_type_2 and end_type_2.strip() != end_type_1.strip():
                end_token = f"{end_type_1}/{end_type_2}"

            return _join_tokens(
                description_lead, mat, method, end_token, thickness_pair, dim_standard
            )

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
            if side1 and side2 and side1 == side2:
                thickness_pair = side1
            elif side1 and side2:
                thickness_pair = f"{side1} x {side2}"
            else:
                thickness_pair = side1 or side2

            if item_code in {"RCS", "RES"}:
                et1u = end_type_1.strip().upper()
                et2u = (end_type_2 or "").strip().upper()
                if et1u == "BE" and et2u == "PE":
                    if side1 and side2 and side1 == side2:
                        end_type_token = "PBE"
                    elif side1 and side2:
                        end_type_token = "BLE/PSE"
                    else:
                        end_type_token = f"{end_type_1}/{end_type_2}".strip("/")
                else:
                    end_type_token = _rcs_res_end_type_token(
                        end_type_1,
                        end_type_2 or end_type_1,
                        reducer_size1,
                        reducer_size2,
                    )
            else:
                end_type_token = end_type_1
                if end_type_2 and end_type_2 != end_type_1:
                    end_type_token = f"{end_type_1}/{end_type_2}"

            dim_disp = _reducer_description_dim_standard(dim_standard)
            return _join_tokens(
                description_lead, mat, method, end_type_token, thickness_pair, dim_disp
            )

        remarks = _get_cell_text(ws, row_idx, header_to_col, "Remarks")
        tokens = [
            description_lead,
            mat,
            method,
            end_type_1,
            fitting_thickness_or_rating,
            remarks,
            dim_standard,
        ]
        return _join_tokens(*tokens)

    if sheet_name == "Flange_Group":
        flange_type_raw = _pick_first_non_empty(
            ws, row_idx, header_to_col, ["Flange_Type", "End_Type"]
        )
        flange_type = _normalize_flange_type_token(flange_type_raw)
        facing = _get_cell_text(ws, row_idx, header_to_col, "Facing")
        mat = _mat_code_grade(ws, row_idx, header_to_col, "Mat_Code")
        rating_raw = _pick_first_non_empty(
            ws, row_idx, header_to_col, ["Rating", "Rating_Thickness"]
        )
        rating_disp = _flange_rating_display(rating_raw)
        # SW/WN만 조인트 파이프와 보어 매칭이 필요하므로 SCH를 설명에 표기.
        show_sch = flange_type in {"SW", "WN"}
        sch_from_table = sch1 if show_sch else ""
        title = description_lead if _to_text(description_lead) else "FLANGE"
        return _join_tokens(
            title, mat, flange_type, rating_disp, facing, sch_from_table, dim_standard
        )

    if sheet_name == "Gasket_Group":
        gasket_type = _get_cell_text(ws, row_idx, header_to_col, "Gasket_Type")
        mat_primary = _get_cell_text(ws, row_idx, header_to_col, "Material_Primary")
        mat_secondary = _get_cell_text(ws, row_idx, header_to_col, "Material_Secondary")
        mat_ir = _get_cell_text(ws, row_idx, header_to_col, "Material_Inner_Ring")
        mat_or = _get_cell_text(ws, row_idx, header_to_col, "Material_Outer_Ring")
        rating = _pick_first_non_empty(ws, row_idx, header_to_col, ["Rating"])
        facing = _get_cell_text(ws, row_idx, header_to_col, "Facing")
        thickness_raw = _get_cell_text(ws, row_idx, header_to_col, "Thickness")
        thickness = _normalize_gasket_thickness(gasket_type, thickness_raw)
        remarks = _get_cell_text(ws, row_idx, header_to_col, "Remarks")
        title = description_lead if _to_text(description_lead) else "GASKET"
        mat_token = _gasket_material_token(gasket_type, mat_primary, mat_secondary)
        ring_token = _join_tokens(
            f"IR-{mat_ir}" if mat_ir else "",
            f"OR-{mat_or}" if mat_or else "",
        )
        rating_disp = _flange_rating_display(rating)
        return _join_tokens(
            title,
            gasket_type,
            mat_token,
            ring_token,
            rating_disp,
            facing,
            thickness,
            remarks,
            dim_standard,
        )

    if _is_valve_sheet(sheet_name):
        valve_type = _get_cell_text(ws, row_idx, header_to_col, "Valve_Type")
        body_mat = _get_cell_text(ws, row_idx, header_to_col, "Body_Mat")
        trim_mat = _get_cell_text_any(
            ws, row_idx, header_to_col, ["Trim_Mat", "Stem/Disc/Ball_Mat"]
        )
        rating = _pick_first_non_empty(ws, row_idx, header_to_col, ["Rating", "Rating_Thickness"])
        end_type = _get_cell_text(ws, row_idx, header_to_col, "End_Type")
        operation = _get_cell_text(ws, row_idx, header_to_col, "Operation")
        bonnet_type = _get_cell_text(ws, row_idx, header_to_col, "Bonnet_Type")
        valve_feature = _get_cell_text_any(
            ws, row_idx, header_to_col, ["Valve_Feature", "Disc_Type"]
        )
        if sheet_name == "Valve_Group":
            code_u = _to_text(item_code).upper()
            op_upper = _to_text(operation).upper()
            seat_mat = _get_cell_text(ws, row_idx, header_to_col, "Seat_Mat")
            trim_token = (
                f"{trim_mat}+{seat_mat}" if trim_mat and seat_mat else (trim_mat or seat_mat)
            )
            operation_token = ""
            if "OS&Y" in op_upper:
                operation_token = "OS&Y"
            elif code_u == "VL":
                operation_token = "FS"
            go_token = "GO" if op_upper.startswith("GR") else ""
            disc_token = ""
            if code_u == "VC":
                disc_token = valve_feature
            elif code_u == "VL":
                size1_num = _to_float(size1_value or "")
                disc_token = "FB" if size1_num is not None and size1_num >= 2.0 else "RB"
            rating_disp = _flange_rating_display(rating)
            return _join_tokens(
                _join_tokens(valve_type, "VALVE"),
                body_mat,
                "/",
                trim_token,
                rating_disp,
                end_type,
                bonnet_type,
                disc_token,
                operation_token,
                go_token,
            )
        trim_segment = f"/ TRIM {trim_mat}" if trim_mat else ""
        return _join_tokens(
            description_lead,
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

    if sheet_name == "Bolt_Group":
        bolt_type_raw = _get_cell_text(ws, row_idx, header_to_col, "Bolt_Type").strip().upper()
        # 출력 기준 산출물과 호환을 위해 STUD는 STUB로 표기 유지.
        bolt_type_token = "STUB" if bolt_type_raw == "STUD" else bolt_type_raw
        bolt_code = _get_cell_text(ws, row_idx, header_to_col, "Bolt_Mat_Code")
        bolt_class = _get_cell_text(ws, row_idx, header_to_col, "Bolt_Mat_Class")
        bolt_mat = (
            f"{bolt_code}-{bolt_class}".strip("-")
            if bolt_code and bolt_class
            else (bolt_code or bolt_class)
        )
        nut_type = _get_cell_text(ws, row_idx, header_to_col, "Nut_Type")
        nut_code = _get_cell_text(ws, row_idx, header_to_col, "Nut_Mat_Code")
        nut_class = _get_cell_text(ws, row_idx, header_to_col, "Nut_Mat_Class")
        nut_mat = (
            f"{nut_code}-{nut_class}".strip("-")
            if nut_code and nut_class
            else (nut_code or nut_class)
        )
        dim_token = _bolt_dim_standard_token(
            _get_cell_text(ws, row_idx, header_to_col, "Bolt_Dim_Standard"),
            _get_cell_text(ws, row_idx, header_to_col, "Nut_Dim_Standard"),
        )
        return _join_tokens(
            bolt_type_token,
            "BOLT",
            bolt_mat,
            "/",
            nut_type,
            "NUT",
            nut_mat,
            dim_token,
        )

    return ""


def _iter_output_rows(
    workbook,
    schedule_rows: list[dict[str, str]],
    reducing_data: dict[str, dict[tuple[str, str], str]],
    class_reducing_codes: dict[str, str],
    item_code_db: dict[str, dict[str, str]],
    class_specs: dict[str, ClassSpec],
    logger: logging.Logger,
    component_mapping: Optional[dict[str, Any]] = None,
    branch_data: Optional[dict[str, dict[tuple[str, str], str]]] = None,
    class_branch_codes: Optional[dict[str, str]] = None,
    class_size_ranges: Optional[dict[str, list[str]]] = None,
):
    mapping = component_mapping if component_mapping is not None else load_component_mapping()
    branch_data = branch_data if branch_data is not None else {}
    class_branch_codes = class_branch_codes if class_branch_codes is not None else {}
    class_size_ranges = class_size_ranges if class_size_ranges is not None else {}

    fitting_ws = workbook["Fitting_Group"] if "Fitting_Group" in workbook.sheetnames else None
    fitting_header_to_col: dict[str, int] = {}
    fitting_header_row: Optional[int] = None
    if fitting_ws is not None:
        try:
            fitting_header_row = _detect_header_row(
                fitting_ws, ["Class_Name", "Item_Code", "End_Type_1"]
            )
            fitting_header_to_col = _build_header_index(fitting_ws, fitting_header_row)
        except ValueError:
            fitting_ws = None
            fitting_header_row = None

    for sheet_config in MATERIAL_SHEET_CONFIGS:
        sheet_name = sheet_config["sheet_name"]

        if sheet_name not in workbook.sheetnames:
            continue

        ws = workbook[sheet_name]
        required_headers = sheet_config["required_headers"]
        size_from_1_header = sheet_config["size_from_1"]
        size_to_1_header = sheet_config["size_to_1"]
        size_from_2_header = sheet_config["size_from_2"]
        size_to_2_header = sheet_config["size_to_2"]
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

            if sheet_name == "Fitting_Group" and item_code in REDUCER_ITEM_CODES_FROM_TABLE:
                for msg in validate_template_row(
                    sheet_name, ws, row_idx, header_to_col, mapping
                ):
                    logger.warning(msg)
                continue

            if sheet_name == "Fitting_Group" and item_code in BRANCH_ITEM_CODES_FROM_TABLE:
                bt_code = class_branch_codes.get(class_name, "")
                if bt_code and branch_data.get(bt_code):
                    for msg in validate_template_row(
                        sheet_name, ws, row_idx, header_to_col, mapping
                    ):
                        logger.warning(msg)
                    continue

            row_issues = validate_template_row(
                sheet_name, ws, row_idx, header_to_col, mapping
            )
            if row_issues:
                for msg in row_issues:
                    logger.warning(msg)
                continue

            size_range_issues: list[str] = []
            size_range_issues.extend(
                validate_size_range_for_row(
                    sheet_name,
                    row_idx,
                    class_name,
                    ws,
                    header_to_col,
                    size_from_1_header,
                    size_to_1_header,
                    class_size_ranges,
                    size_label="Size1" if size_from_2_header else "Size",
                )
            )
            if size_from_2_header and size_to_2_header:
                size_range_issues.extend(
                    validate_size_range_for_row(
                        sheet_name,
                        row_idx,
                        class_name,
                        ws,
                        header_to_col,
                        size_from_2_header,
                        size_to_2_header,
                        class_size_ranges,
                        size_label="Size2",
                    )
                )
            if size_range_issues:
                for msg in size_range_issues:
                    logger.error(msg)
                continue

            log_class_constraint_warnings(
                logger, sheet_name, class_name, row_idx, ws, header_to_col, class_specs
            )

            db_row: Optional[dict[str, str]] = None
            if item_code:
                db_row = item_code_db.get(item_code)
                if not db_row:
                    logger.warning(
                        f"Item_Code not in DB (Item_Name left empty): {item_code!r}"
                    )

            catalog_item_name = db_row["Item_Name"] if db_row else ""
            description_prefix = (
                (db_row.get("Description_Prefix") or catalog_item_name) if db_row else ""
            )
            db_group = db_row.get("Group") if db_row else None

            code_u = _to_text(item_code).upper()
            if sheet_name == "Fitting_Group" and code_u in ELBOW_LR_SR_ITEM_CODES:
                catalog_item_name = _strip_trailing_lr_sr(catalog_item_name)
                dim_std = _get_cell_text(ws, row_idx, header_to_col, "Dim_Standard")
                end_t1 = _get_cell_text(ws, row_idx, header_to_col, "End_Type_1")
                rating_c = _get_cell_text(ws, row_idx, header_to_col, "Rating")
                if _fitting_elbow_should_strip_lr_sr(code_u, dim_std, end_t1, rating_c):
                    description_prefix = _strip_trailing_lr_sr(description_prefix)

            desc_lead = description_prefix
            if _is_valve_sheet(sheet_name) and not desc_lead:
                desc_lead = _get_cell_text(ws, row_idx, header_to_col, "Valve_Type")

            size_from_1 = _get_cell_text(ws, row_idx, header_to_col, size_from_1_header)
            size_to_1 = _get_cell_text(ws, row_idx, header_to_col, size_to_1_header)
            size2_display = _format_size2(
                _get_cell_text(ws, row_idx, header_to_col, size_from_2_header),
                _get_cell_text(ws, row_idx, header_to_col, size_to_2_header),
            )

            remarks = _get_cell_text(ws, row_idx, header_to_col, "Remarks")

            exploded_sizes = _explode_size_range(size_from_1, size_to_1)
            if not exploded_sizes:
                size1_out = size_from_1 or size_to_1
                th1 = lookup_schedule_thickness(schedule_rows, class_name, size1_out)
                th2 = ""
                if sheet_name == "Bolt_Group" or _is_valve_sheet(sheet_name):
                    th1 = ""
                    th2 = ""
                if size2_display:
                    if "-" not in size2_display:
                        th2 = lookup_schedule_thickness(schedule_rows, class_name, size2_display)
                    else:
                        part = size2_display.split("-", 1)[0].strip()
                        th2 = lookup_schedule_thickness(schedule_rows, class_name, part)

                nip = (
                    _try_nipple_pipe_output(
                        item_code,
                        ws,
                        row_idx,
                        header_to_col,
                        th1,
                        catalog_item_name,
                        description_prefix,
                    )
                    if sheet_name == "Pipe_Group"
                    else None
                )
                if nip:
                    desc, out_item_name, out_remarks = nip
                else:
                    if sheet_name == "Gasket_Group":
                        gasket_type = _get_cell_text(ws, row_idx, header_to_col, "Gasket_Type")
                        thickness_raw = _get_cell_text(ws, row_idx, header_to_col, "Thickness")
                        th1 = _normalize_gasket_thickness(gasket_type, thickness_raw)
                        th2 = ""
                    desc = _build_item_description_by_rule(
                        sheet_name,
                        ws,
                        row_idx,
                        header_to_col,
                        item_code,
                        desc_lead,
                        th1,
                        th2,
                        db_group=db_group,
                        size1_value=size1_out,
                        class_design_code=_class_design_code_for(class_specs, class_name),
                    )
                    out_item_name = catalog_item_name
                    if sheet_name == "Bolt_Group" and not out_item_name:
                        out_item_name = "BOLT&NUT"
                    if _is_valve_sheet(sheet_name) and not out_item_name:
                        valve_type = _get_cell_text(ws, row_idx, header_to_col, "Valve_Type")
                        out_item_name = _join_tokens(valve_type, "VALVE")
                    out_remarks = remarks
                yield {
                    "Class_Name": class_name,
                    "Item_Code": item_code,
                    "Size1": size1_out,
                    "Size2": size2_display,
                    "Thickness1": th1,
                    "Thickness2": th2,
                    "Commodity_Code": "",
                    "Item_Description": desc,
                    "Item_Name": out_item_name,
                    "Remarks": out_remarks,
                    "__template_row_idx": row_idx,
                }
                continue

            for exploded_size in exploded_sizes:
                th1 = lookup_schedule_thickness(schedule_rows, class_name, exploded_size)
                th2 = ""
                if sheet_name == "Bolt_Group" or _is_valve_sheet(sheet_name):
                    th1 = ""
                    th2 = ""
                if size2_display:
                    if "-" not in size2_display:
                        th2 = lookup_schedule_thickness(schedule_rows, class_name, size2_display)
                    else:
                        part = size2_display.split("-", 1)[0].strip()
                        th2 = lookup_schedule_thickness(schedule_rows, class_name, part)

                nip = (
                    _try_nipple_pipe_output(
                        item_code,
                        ws,
                        row_idx,
                        header_to_col,
                        th1,
                        catalog_item_name,
                        description_prefix,
                    )
                    if sheet_name == "Pipe_Group"
                    else None
                )
                if nip:
                    desc, out_item_name, out_remarks = nip
                else:
                    if sheet_name == "Gasket_Group":
                        gasket_type = _get_cell_text(ws, row_idx, header_to_col, "Gasket_Type")
                        thickness_raw = _get_cell_text(ws, row_idx, header_to_col, "Thickness")
                        th1 = _normalize_gasket_thickness(gasket_type, thickness_raw)
                        th2 = ""
                    desc = _build_item_description_by_rule(
                        sheet_name,
                        ws,
                        row_idx,
                        header_to_col,
                        item_code,
                        desc_lead,
                        th1,
                        th2,
                        db_group=db_group,
                        size1_value=exploded_size,
                        class_design_code=_class_design_code_for(class_specs, class_name),
                    )
                    out_item_name = catalog_item_name
                    if sheet_name == "Bolt_Group" and not out_item_name:
                        out_item_name = "BOLT&NUT"
                    if _is_valve_sheet(sheet_name) and not out_item_name:
                        valve_type = _get_cell_text(ws, row_idx, header_to_col, "Valve_Type")
                        out_item_name = _join_tokens(valve_type, "VALVE")
                    out_remarks = remarks
                yield {
                    "Class_Name": class_name,
                    "Item_Code": item_code,
                    "Size1": exploded_size,
                    "Size2": size2_display,
                    "Thickness1": th1,
                    "Thickness2": th2,
                    "Commodity_Code": "",
                    "Item_Description": desc,
                    "Item_Name": out_item_name,
                    "Remarks": out_remarks,
                    "__template_row_idx": row_idx,
                }

    if fitting_ws is None or fitting_header_row is None:
        return

    # Reducing_Table 기반 추가 생성 (RD/SN -> RC/RE/RCS/RES 분해)
    if reducing_data:
        reducer_constraint_logged: set[tuple[str, str]] = set()

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
                    nominal_mode_cls = _class_nominal_mode_for(class_specs, class_name)
                    template_row_idx = _find_fitting_template_row_for_nps(
                        fitting_ws,
                        fitting_header_row,
                        fitting_header_to_col,
                        class_name,
                        mapped_code,
                        size1,
                        logger,
                        nominal_mode_cls,
                        log_if_missing=False,
                    )
                    if template_row_idx is None:
                        logger.warning(
                            f"Fitting_Group template row missing for class/item/size: "
                            f"{class_name}/{mapped_code}/{size1}"
                        )
                        continue

                    reducer_issues = validate_template_row(
                        "Fitting_Group",
                        fitting_ws,
                        template_row_idx,
                        fitting_header_to_col,
                        mapping,
                    )
                    if reducer_issues:
                        for msg in reducer_issues:
                            logger.warning(msg)
                        continue

                    log_key = (class_name, mapped_code)
                    if log_key not in reducer_constraint_logged:
                        reducer_constraint_logged.add(log_key)
                        log_class_constraint_warnings(
                            logger,
                            "Fitting_Group",
                            class_name,
                            template_row_idx,
                            fitting_ws,
                            fitting_header_to_col,
                            class_specs,
                        )

                    db_row = item_code_db.get(mapped_code, {})
                    catalog_out = _to_text(db_row.get("Item_Name", ""))
                    desc_lead_red = _to_text(
                        db_row.get("Description_Prefix") or db_row.get("Item_Name", "")
                    )
                    db_group = _to_text(db_row.get("Group", ""))
                    th1 = lookup_schedule_thickness(
                        schedule_rows, class_name, size1, nominal_mode_cls
                    )
                    th2 = lookup_schedule_thickness(
                        schedule_rows, class_name, size2, nominal_mode_cls
                    )
                    desc = _build_item_description_by_rule(
                        "Fitting_Group",
                        fitting_ws,
                        template_row_idx,
                        fitting_header_to_col,
                        mapped_code,
                        desc_lead_red,
                        th1,
                        th2,
                        db_group=db_group,
                        reducer_size1=size1,
                        reducer_size2=size2,
                        class_design_code=_class_design_code_for(class_specs, class_name),
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
                        "Item_Name": catalog_out,
                        "Remarks": "",
                    }

    # Branch_Table 기반 T / RT / TH
    # - T: 등경 티
    # - RT: 이경 티
    # - TH: Half Coupling (run size 영향 없이 branch size(Size2) 기준으로만 전개)
    if branch_data:
        branch_constraint_logged: set[tuple[str, str]] = set()

        for class_name, table_code in class_branch_codes.items():
            size_map = branch_data.get(table_code, {})
            if not size_map:
                continue
            # TH는 Size1(주배관)에 따라 품목/치수가 달라지지 않으므로
            # 같은 Size2는 1회만 전개한다.
            th_seen_branch_sizes: set[str] = set()

            for (size1, size2), item_t in size_map.items():
                it = item_t.strip().upper()
                if it == "T":
                    mapped_code = "T"
                    use_dual = False
                elif it == "RT":
                    mapped_code = "RT"
                    use_dual = True
                elif it == "TH":
                    mapped_code = "TH"
                    use_dual = False
                else:
                    logger.warning(
                        f"Branch_Table unknown Item_Type {item_t!r} ({table_code} {size1}x{size2}); skipped"
                    )
                    continue

                if mapped_code == "TH":
                    size2_key = _to_text(size2)
                    if not size2_key:
                        logger.warning(
                            f"Branch_Table TH has empty branch size ({table_code} {size1}x{size2}); skipped"
                        )
                        continue
                    if size2_key in th_seen_branch_sizes:
                        continue
                    th_seen_branch_sizes.add(size2_key)
                    th_output_size = size2_key
                else:
                    th_output_size = ""

                nominal_mode_cls = _class_nominal_mode_for(class_specs, class_name)
                if mapped_code == "RT":
                    template_row_idx = _find_rt_fitting_template_row(
                        fitting_ws,
                        fitting_header_row,
                        fitting_header_to_col,
                        class_name,
                        size1,
                        size2,
                        logger,
                        nominal_mode_cls,
                    )
                elif mapped_code == "TH":
                    template_row_idx = _find_fitting_template_row_for_nps(
                        fitting_ws,
                        fitting_header_row,
                        fitting_header_to_col,
                        class_name,
                        mapped_code,
                        th_output_size,
                        logger,
                        nominal_mode_cls,
                    )
                else:
                    template_row_idx = _find_fitting_template_row_for_nps(
                        fitting_ws,
                        fitting_header_row,
                        fitting_header_to_col,
                        class_name,
                        mapped_code,
                        size1,
                        logger,
                        nominal_mode_cls,
                    )
                if template_row_idx is None:
                    continue

                branch_issues = validate_template_row(
                    "Fitting_Group",
                    fitting_ws,
                    template_row_idx,
                    fitting_header_to_col,
                    mapping,
                )
                if branch_issues:
                    for msg in branch_issues:
                        logger.warning(msg)
                    continue

                log_key_b = (class_name, mapped_code)
                if log_key_b not in branch_constraint_logged:
                    branch_constraint_logged.add(log_key_b)
                    log_class_constraint_warnings(
                        logger,
                        "Fitting_Group",
                        class_name,
                        template_row_idx,
                        fitting_ws,
                        fitting_header_to_col,
                        class_specs,
                    )

                db_row_b = item_code_db.get(mapped_code, {})
                catalog_b = _to_text(db_row_b.get("Item_Name", ""))
                desc_lead_b = _to_text(
                    db_row_b.get("Description_Prefix") or db_row_b.get("Item_Name", "")
                )
                db_group_b = _to_text(db_row_b.get("Group", ""))
                if mapped_code == "TH":
                    th1b = lookup_schedule_thickness(
                        schedule_rows, class_name, th_output_size, nominal_mode_cls
                    )
                    th2b = ""
                else:
                    th1b = lookup_schedule_thickness(
                        schedule_rows, class_name, size1, nominal_mode_cls
                    )
                    th2b = lookup_schedule_thickness(
                        schedule_rows, class_name, size2, nominal_mode_cls
                    )

                desc_b = _build_item_description_by_rule(
                    "Fitting_Group",
                    fitting_ws,
                    template_row_idx,
                    fitting_header_to_col,
                    mapped_code,
                    desc_lead_b,
                    th1b,
                    th2b,
                    db_group=db_group_b,
                    fitting_dual_schedule=use_dual,
                    class_design_code=_class_design_code_for(class_specs, class_name),
                )

                yield {
                    "Class_Name": class_name,
                    "Item_Code": mapped_code,
                    "Size1": th_output_size if mapped_code == "TH" else size1,
                    "Size2": "" if mapped_code == "TH" else size2,
                    "Thickness1": th1b,
                    "Thickness2": th2b,
                    "Commodity_Code": "",
                    "Item_Description": desc_b,
                    "Item_Name": catalog_b,
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

    from template_generator import ensure_all_program_data_files

    ensure_all_program_data_files()
    item_code_db = _load_item_code_db(logger)
    component_mapping = load_component_mapping()

    in_wb = load_workbook(template_path, data_only=True)
    schedule_rows = load_schedule_rows(in_wb)
    class_specs = load_class_specs_from_workbook(in_wb)
    class_size_ranges = load_class_size_ranges(in_wb)

    size_range_errors: list[str] = []
    if class_size_ranges and "Schedule" in in_wb.sheetnames:
        _sch_ws = in_wb["Schedule"]
        try:
            _sch_hr = _detect_header_row(_sch_ws, ["Class_Name", "Size_From", "Size_To"])
            _sch_htc = _build_header_index(_sch_ws, _sch_hr)
            for _r in range(_sch_hr + 1, _sch_ws.max_row + 1):
                _cn = _get_cell_text(_sch_ws, _r, _sch_htc, "Class_Name")
                if not _cn:
                    continue
                for _msg in validate_size_range_for_row(
                    "Schedule",
                    _r,
                    _cn,
                    _sch_ws,
                    _sch_htc,
                    "Size_From",
                    "Size_To",
                    class_size_ranges,
                    size_label="Size",
                ):
                    size_range_errors.append(_msg)
        except ValueError:
            pass
    if size_range_errors:
        for _m in size_range_errors:
            logger.error(_m)
        raise ValueError(
            "Schedule Size_From/Size_To outside Class Size Range; "
            "fix Class_Size_Range sheet or Schedule rows."
        )

    reducing_data = _load_reducing_table(in_wb)
    class_reducing_codes = _load_class_reducing_table_codes(in_wb)
    branch_data = _load_branch_table(in_wb)
    class_branch_codes = _load_class_branch_table_codes(in_wb)

    def _check_size_table(
        table_label: str,
        class_code_map: dict[str, str],
        table_payload: dict[str, dict[tuple[str, str], str]],
    ) -> list[str]:
        errs: list[str] = []
        if not class_size_ranges:
            return errs
        for _class_name, _code in class_code_map.items():
            _code = (_code or "").strip()
            if not _code:
                continue
            _active = class_size_ranges.get(_class_name)
            if _active is None:
                continue
            _active_set = {str(s).strip() for s in _active if str(s).strip()}
            if not _active_set:
                continue
            _payload = table_payload.get(_code) or {}
            for (_s1, _s2), _ in _payload.items():
                for _label, _val in (("Size1", _s1), ("Size2", _s2)):
                    _t = str(_val).strip()
                    if _t and _t not in _active_set:
                        errs.append(
                            f"{table_label} (Class {_class_name!r}, Table {_code!r}): "
                            f"{_label} {_t!r} is outside Class Size Range."
                        )
        return errs

    table_range_errors = _check_size_table(
        "Reducing_Table", class_reducing_codes, reducing_data
    )
    table_range_errors.extend(
        _check_size_table("Branch_Table", class_branch_codes, branch_data)
    )
    if table_range_errors:
        for _m in table_range_errors:
            logger.error(_m)
        raise ValueError(
            "Reducing/Branch table size outside Class Size Range; "
            "fix Class_Size_Range sheet or table entries."
        )
    ca_errors, ca_warnings = corrosion_allowance_validation_messages(in_wb)
    for msg in ca_warnings:
        logger.warning(msg)
    if ca_errors:
        raise ValueError("; ".join(ca_errors))

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
            class_specs,
            logger,
            component_mapping,
            branch_data=branch_data,
            class_branch_codes=class_branch_codes,
            class_size_ranges=class_size_ranges,
        )
    )
    def _sort_size2_key(r: dict[str, Any]) -> tuple:
        """RT/T 는 Size2 를 NPS 숫자로, 그 외(Reducing_Table 전개 등)는 문자열 순으로 정렬(기존 산출물과 동일)."""
        ic = _to_text(r.get("Item_Code"))
        t2 = _to_text(r.get("Size2"))
        f2 = _to_float(t2)
        if ic in ("RT", "T"):
            return (0, f2 if f2 is not None else -1.0, t2)
        return (1, t2)

    def _sort_size1_key(r: dict[str, Any]) -> tuple:
        ic = _to_text(r.get("Item_Code"))
        s1 = _to_text(r.get("Size1"))
        f1 = _to_float(s1)
        if ic == "B":
            desc = _to_text(r.get("Item_Description")).upper()
            bolt_desc_key = (0, desc) if desc.startswith("STUB BOLT ") else (1, desc)
            return (0, bolt_desc_key, f1 if f1 is not None else 10**9, s1)
        return (1, f1 if f1 is not None else 10**9, s1)

    rows.sort(
        key=lambda r: (
            _to_text(r.get("Class_Name")),
            _item_code_priority(_to_text(r.get("Item_Code"))),
            (
                _to_text(r.get("Item_Code"))
                if _item_code_priority(_to_text(r.get("Item_Code")))
                < len(ITEM_CODE_OUTPUT_ORDER)
                else ""
            ),
            int(r.get("__template_row_idx", 0) or 0),
            _sort_size1_key(r),
            _sort_size2_key(r),
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
