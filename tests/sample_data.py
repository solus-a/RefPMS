"""테스트 공용 샘플 — Class 1개(A1) + Component 13그룹.

값(Size Selection 포함)은 데이터 파일에서 자동으로 고르지 않고 리터럴로 고정한다.
데이터 파일이 바뀌어도 테스트 기준이 흔들리지 않게 하고, 바뀐 값이 기대와 다르면
테스트가 드러내게 하려는 것.

Size 범위는 같은 Item_Code 를 쓰는 Forged(0.5~1.5)와 Wrought(2~24)가 겹치지 않게
잡아, 산출물 행(그룹 컬럼 없음)을 크기로 원래 그룹에 되돌려 매칭할 수 있게 했다.
소구경은 단조 SW, 대구경은 BW·주조 밸브 FLGD 로 실무 관행에 맞춘다.
"""
from __future__ import annotations

from class_level_model import (
    ClassLevelBundle,
    ClassTemplateGlobalSettings,
    SizeSelection,
    row_dict_for_headers,
)
from units_notation_headers import class_define_storage_headers

CLASS = "A1"

# Global Size Selection — 1.25 / 2.5 / 3.5 / 5 / 22 는 일부러 제외 (F4 검증용).
SELECTED_NPS = ["0.5", "0.75", "1", "1.5", "2", "3", "4", "6", "8", "10", "12", "14", "16", "18", "20", "24"]
SELECTED_DN = ["15", "20", "25", "40", "50", "80", "100", "150", "200", "250", "300", "350", "400", "450", "500", "600"]


def _row(item_code: str, size_from: str, size_to: str, *, uses_size1: bool = False, **fields: str) -> dict[str, str]:
    row = {"Class_Name": CLASS, "Item_Code": item_code}
    if uses_size1:
        row.update({"Size1_From": size_from, "Size1_To": size_to})
    else:
        row.update({"Size_From": size_from, "Size_To": size_to})
    row.update(fields)
    row.setdefault("Option_Code", "001")
    row.setdefault("Remarks", "")
    return row


_CS = {"Matl_Category": "CS", "Matl_Std": "ASTM"}
_VALVE = {**_CS, "Matl_Code": "A216-WCB", "Rating": "CL150"}
_LARGE = ("2", "24")


def component_rows() -> dict[str, list[dict[str, str]]]:
    pipe = {**_CS, "Matl_Code": "A106-B", "Manufacturing_Method": "SMLS", "End_Type": "PE"}
    forged = {**_CS, "Matl_Code": "A105", "Rating": "CL2000", "End_Type": "SW"}
    wrought = {**_CS, "Matl_Code": "A234-WPB", "Manufacturing_Method": "SMLS", "End_Type": "BW"}
    flange = {**_CS, "Matl_Code": "A105", "Rating": "CL150", "Facing": "RF", "Flange_Type": "WN",
              "Size2_From": "", "Size2_To": ""}
    return {
        "Pipe_Group": [
            _row("P", "0.5", "1.5", Length="", **pipe),
            _row("P", "2", "24", Length="", **pipe),
            _row("JN", "0.5", "1.5", Length="50mm", **pipe),
        ],
        "Forged_Fitting_Group": [_row(c, "0.5", "1.5", **forged) for c in ("E", "T", "CP")],
        "Wrought_Fitting_Group": [_row(c, "2", "24", **wrought) for c in ("E", "E4", "T", "CP")],
        # Blind(FB)는 Flange_Type 강제 문제(F10) 때문에 공용 샘플에서 제외 — test_validation 참고.
        "Flange_Group": [_row("F", "0.5", "24", uses_size1=True, **flange)],
        "Gasket_Group": [
            _row("G", "0.5", "24", Gasket_Type="SHEET", Material_Primary="COMPRESSED NON-ASBESTOS",
                 Material_Secondary="ARAMID FIBER+NBR", Rating="CL150", Facing="RF", Thickness="1.5mm"),
        ],
        "Bolt_Group": [
            _row("B", "0.5", "24", Bolt_Type="STUD BOLT", Bolt_Matl_Category="CS", Bolt_Matl_Std="ASTM",
                 Bolt_Matl_Code="A307-B", Nut_Type="HEX NUTS", Nut_Matl_Std="ASTM",
                 Nut_Matl_Code="A194-2H", Bolt_Length_Table="BLT-CL150"),
        ],
        "Gate_Valve_Group": [
            _row("VA", *_LARGE, uses_size1=True, **_VALVE, Trim_Matl="13CR", End_Type="FLGD RF",
                 Bonnet_Stem="BB OS&Y", Wedge_Type="SOLID", Operation="HW"),
        ],
        "Globe_Valve_Group": [
            _row("VB", *_LARGE, uses_size1=True, **_VALVE, Trim_Matl="13CR", End_Type="FLGD RF",
                 Bonnet_Stem="BB OS&Y", Operation="HW", Disc_Type="PLUG"),
        ],
        "Check_Valve_Group": [
            _row("VC", *_LARGE, uses_size1=True, **_VALVE, Trim_Matl="13CR", End_Type="FLGD RF",
                 Cover_Disc="BC SWING"),
        ],
        "Ball_Valve_Group": [
            _row("VL", *_LARGE, uses_size1=True, **_VALVE, Trim_Matl="SS316", Seat_Matl="PTFE",
                 End_Type="FLGD RF", Bore="FB", Entry_Type="TOP ENTRY", Operation="HW"),
        ],
        "Butterfly_Valve_Group": [
            _row("VU", *_LARGE, uses_size1=True, **_VALVE, Disc_Matl="SS316", Seat_Matl="EPDM",
                 Body_Type="WAFER", Operation="HW", Disc_Type="CONCENTRIC"),
        ],
        "Plug_Valve_Group": [
            _row("VP", *_LARGE, uses_size1=True, **_VALVE, Plug_Matl="SS316", Seat_Matl="PTFE",
                 End_Type="FLGD RF", Operation="HW", Plug_Type="LUBRICATED"),
        ],
        # 소구경 단조 계장 밸브. 실무 표준 CL800 은 Rating 선택지에 없어 CL150 사용 — F11.
        "Needle_Valve_Group": [
            _row("VN", "0.5", "1", uses_size1=True, **{**_VALVE, "Matl_Code": "A105"}, Trim_Matl="SS316",
                 Seat_Matl="PTFE", End_Type="SW", Bonnet_Stem="BB OS&Y", Operation="HW",
                 Disc_Type="NEEDLE"),
        ],
    }


def class_row(**overrides: str) -> dict[str, str]:
    row = row_dict_for_headers(class_define_storage_headers())
    row.update({
        "Class_Name": CLASS, "Revision_No": "0", "Nominal_Size_System": "NPS",
        "Size_From": "0.5", "Size_To": "24", "Design_Code": "ASME B31.3",
        "Class_Base_Material": "KCS", "Class_Rating": "CL150", "Corrosion_Allowance": "1.5",
        "Design_Temperature_From": "-29", "Design_Temperature_To": "200",
        # CL150(Group 1.1) 200°C 허용 압력 약 13.8 barg 이내.
        "Design_Pressure_From": "0", "Design_Pressure_To": "12",
        "Fluid_Service": "PROCESS",
    })
    row.update(overrides)
    return row


def schedule_rows() -> list[dict[str, str]]:
    return [
        {"Class_Name": CLASS, "Size_From": "0.5", "Size_To": "1.5", "Schedule": "SCH80"},
        {"Class_Name": CLASS, "Size_From": "2", "Size_To": "24", "Schedule": "STD"},
    ]


def build_sample_bundle() -> ClassLevelBundle:
    return ClassLevelBundle(
        class_define_rows=[class_row()],
        schedule_rows=schedule_rows(),
        reducing_tables=[],
        branch_tables=[],
        global_settings=ClassTemplateGlobalSettings(
            unit_system="SI",
            design_temperature_unit="°C",
            design_pressure_unit="barg",
            size_selection=SizeSelection(nps=list(SELECTED_NPS), dn=list(SELECTED_DN)),
        ),
        component_rows=component_rows(),
    )
