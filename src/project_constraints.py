"""프로젝트 최상위 제약: 병합된 설정 dict 검증 (비즈니스 규칙 전제)."""

from __future__ import annotations

from typing import Any


def _validate_design_units_nested(errors: list[str], un: dict[str, Any]) -> None:
    """
    ``unit_system.design_units.Metric`` / ``...Imperial`` 에
    temperature·pressure {{allowed, selected}} 검사.
    """
    us_block = un.get("unit_system")
    if not isinstance(us_block, dict):
        return

    legacy = un.get("design_units")
    nested = us_block.get("design_units")
    if isinstance(legacy, dict) and not isinstance(nested, dict):
        errors.append(
            "units_notation: 최상위 design_units 는 사용하지 않습니다. "
            "unit_system.design_units 로 옮기세요."
        )
        return

    du = nested
    if not isinstance(du, dict):
        errors.append(
            "units_notation.unit_system.design_units: "
            "\"Metric\"·\"Imperial\" 키를 가진 객체가 필요합니다."
        )
        return

    active = str(us_block.get("selected", "")).strip()

    for sys_name in ("Metric", "Imperial"):
        blk = du.get(sys_name)
        if not isinstance(blk, dict):
            errors.append(
                f"units_notation.unit_system.design_units.{sys_name}: 객체가 필요합니다."
            )
            continue
        for axis in ("temperature", "pressure"):
            sub = blk.get(axis)
            prefix = f"units_notation.unit_system.design_units.{sys_name}.{axis}"
            if not isinstance(sub, dict):
                errors.append(
                    f'{prefix}: {{ "allowed": [...], "selected": "..." }} 형태여야 합니다.'
                )
                continue
            allowed = sub.get("allowed")
            if not isinstance(allowed, list) or not allowed:
                errors.append(f"{prefix}.allowed: 비어 있지 않은 배열이 필요합니다.")
            chosen = str(sub.get("selected", "") or "").strip()
            if not chosen:
                errors.append(f"{prefix}.selected: 비어 있으면 안 됩니다.")
            elif isinstance(allowed, list) and allowed and chosen not in allowed:
                errors.append(
                    f"{prefix}.selected: 허용 목록 {allowed!r} 안에 없습니다: {chosen!r}"
                )

    if active in ("Metric", "Imperial") and isinstance(du, dict):
        if not isinstance(du.get(active), dict):
            errors.append(
                "units_notation.unit_system.design_units: "
                f"unit_system.selected 가 {active!r} 인데 해당 블록이 없습니다."
            )


def validate_project_constraints(merged: dict[str, Any]) -> list[str]:
    """
    config 병합 결과 전체를 검사합니다.
    반환: 비어 있으면 통과, 아니면 사람이 읽을 수 있는 오류/경고 문장 목록.
    """
    errors: list[str] = []

    un = merged.get("units_notation")
    if not isinstance(un, dict):
        errors.append("units_notation: 누락되었거나 객체가 아닙니다.")
    else:
        us_block = un.get("unit_system")
        if not isinstance(us_block, dict):
            errors.append(
                'units_notation.unit_system: { "allowed": [...], "selected": ..., '
                '"design_units": { "Metric": {...}, "Imperial": {...} } } 형태여야 합니다.'
            )
        else:
            allowed_us = us_block.get("allowed")
            if not isinstance(allowed_us, list) or not allowed_us:
                errors.append("units_notation.unit_system.allowed: Metric/Imperial 목록이 비어 있으면 안 됩니다.")
            sel_us = str(us_block.get("selected", "")).strip()
            if not sel_us:
                errors.append("units_notation.unit_system.selected: 비어 있으면 안 됩니다.")
            elif sel_us not in ("Metric", "Imperial"):
                errors.append(
                    "units_notation.unit_system.selected: Metric 또는 Imperial 만 허용됩니다."
                )
            elif isinstance(allowed_us, list) and allowed_us and sel_us not in allowed_us:
                errors.append(
                    f"units_notation.unit_system.selected: 허용 목록 {allowed_us!r} 안에 없습니다: {sel_us!r}"
                )

        pt = un.get("pipe_thread")
        if not isinstance(pt, dict):
            errors.append(
                "units_notation.pipe_thread: 파이프 밀봉용 나사(NPT/PT 등) 객체가 필요합니다."
            )
        else:
            std = str(pt.get("selected", "") or pt.get("standard", "")).strip()
            if not std:
                errors.append(
                    "units_notation.pipe_thread.selected: 비어 있으면 안 됩니다 (예: NPT, PT)."
                )
            else:
                allowed_pt = pt.get("allowed")
                if isinstance(allowed_pt, list) and allowed_pt and std not in allowed_pt:
                    errors.append(
                        f"units_notation.pipe_thread.selected: 허용 목록 {allowed_pt!r} 안에 없습니다: {std!r}"
                    )

        bt = un.get("bolt_thread")
        if not isinstance(bt, dict):
            errors.append(
                "units_notation.bolt_thread: 볼트·스터드 기계 나사(Metric/Imperial) 객체가 필요합니다."
            )
        else:
            sys_bt = str(bt.get("selected", "") or bt.get("system", "")).strip()
            if not sys_bt:
                errors.append("units_notation.bolt_thread.selected: 비어 있으면 안 됩니다.")
            elif sys_bt not in ("Metric", "Imperial"):
                errors.append(
                    "units_notation.bolt_thread.selected: Metric 또는 Imperial 만 허용됩니다."
                )
            else:
                allowed_bt = bt.get("allowed")
                if isinstance(allowed_bt, list) and allowed_bt and sys_bt not in allowed_bt:
                    errors.append(
                        f"units_notation.bolt_thread.selected: 허용 목록 {allowed_bt!r} 안에 없습니다: {sys_bt!r}"
                    )

        ns = un.get("nominal_size")
        if not isinstance(ns, dict):
            errors.append("units_notation.nominal_size: 객체로 정의해야 합니다.")
        else:
            allowed = ns.get("allowed")
            if not isinstance(allowed, list) or not allowed:
                errors.append(
                    "units_notation.nominal_size.allowed: NPS/DN 등 허용 목록이 비어 있으면 안 됩니다."
                )
            sel = str(ns.get("selected", "")).strip()
            if sel and isinstance(allowed, list) and allowed and sel not in allowed:
                errors.append(
                    f"units_notation.nominal_size.selected: 허용 목록 {allowed!r} 안에 없습니다: {sel!r}"
                )

        _validate_design_units_nested(errors, un)

    # piping_design_codes.selected (e.g. ASME B31.3) 전제로 소켓·나사 단조이음관 치수는 ASME B16.11 계열을
    # 엔진에서 암시 적용(pms_generator: End_Type 기준). 별도 component Dim_Standard 열로 중복 정의하지 않음.
    pdc = merged.get("piping_design_codes")
    if not isinstance(pdc, dict):
        errors.append("piping_design_codes: 누락되었거나 객체가 아닙니다.")
    else:
        al = pdc.get("allowed")
        if not isinstance(al, list) or not al:
            errors.append("piping_design_codes.allowed: 설계 코드 목록이 비어 있으면 안 됩니다.")
        else:
            sel = str(pdc.get("selected", "")).strip()
            if not sel:
                errors.append("piping_design_codes.selected: 비어 있으면 안 됩니다 (기본: ASME B31.3).")
            elif sel not in al:
                errors.append(
                    f"piping_design_codes.selected: 허용 목록 {al!r} 안에 없습니다: {sel!r}"
                )

    cat = merged.get("nps_catalog")
    if not isinstance(cat, dict):
        errors.append("nps_catalog: 프로그램 내장 카탈로그(data/nps_catalog.json)가 로드되지 않았습니다.")
    else:
        un_m = merged.get("units_notation")
        nominal_sel = ""
        if isinstance(un_m, dict):
            ns_m = un_m.get("nominal_size")
            if isinstance(ns_m, dict):
                nominal_sel = str(ns_m.get("selected", "")).strip().upper()
        use_dn = nominal_sel == "DN"

        key = "dn" if use_dn else "nps"
        entries = cat.get(key)
        if not isinstance(entries, list) or not entries:
            errors.append(
                f"nps_catalog.{key}: 카탈로그가 비어 있습니다 (nominal_size.selected={nominal_sel!r})."
            )

    ost = merged.get("output_settings")
    if not isinstance(ost, dict):
        errors.append("output_settings: 누락되었거나 객체가 아닙니다.")
    else:
        if not str(ost.get("filename", "")).strip():
            errors.append("output_settings.filename: 비어 있으면 안 됩니다.")
        if not str(ost.get("sheet_name", "")).strip():
            errors.append("output_settings.sheet_name: 비어 있으면 안 됩니다.")
        cols = ost.get("columns")
        if not isinstance(cols, list) or not cols:
            errors.append("output_settings.columns: 최소 한 개 컬럼이 필요합니다.")
        order = ost.get("item_order")
        if not isinstance(order, list):
            errors.append("output_settings.item_order: 배열이어야 합니다.")

    return errors
