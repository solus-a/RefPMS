"""템플릿·데이터 보조 파일 생성용 기본 내용 (JSON 직렬화).

DEFAULT_COMPONENT_MAPPING 의 모든 행 검증 규칙(required_non_empty,
conditional_required, conditional_empty, code_category_consistency)은
domain_schema(SSOT)에서 도출한다. 이 파일은 규칙을 직접 정의하지 않는다.
"""

from __future__ import annotations

import domain_schema as _domain_schema

DEFAULT_CLASS_MATERIAL_MAPPING: dict = {
    "description": "Class_Base_Material 키(로드 시 대문자) → 부품 Mat 문자열에 포함될 허용 토큰.",
    "base_material_allowlist": {
        "KCS": [
            "A106",
            "A105",
            "A234",
            "A333",
            "A672",
            "A420",
            "A694",
            "A53",
        ]
    },
}

DEFAULT_COMPONENT_MAPPING: dict = {
    "version": 1,
    "description": (
        "부품군(시트)별 템플릿 행 검증 규칙. 컬럼이 시트에 없으면 해당 규칙은 건너뜀. "
        "모든 규칙은 domain_schema(SSOT)에서 도출 — 여기서 직접 정의하지 않는다."
    ),
    "sheets": {},
}

# 전 규칙을 domain_schema(SSOT)에서 도출. 빈 규칙은 키를 생략(기존 구조 유지).
for _sheet in _domain_schema.GROUPS:
    _rules: dict = {"required_non_empty": _domain_schema.required_fields(_sheet)}
    _cr = _domain_schema.conditional_required(_sheet)
    if _cr:
        _rules["conditional_required"] = _cr
    _ce = _domain_schema.conditional_empty(_sheet)
    if _ce:
        _rules["conditional_empty"] = _ce
    _cc = _domain_schema.code_category_consistency(_sheet)
    if _cc:
        _rules["code_category_consistency"] = _cc
    DEFAULT_COMPONENT_MAPPING["sheets"][_sheet] = _rules
