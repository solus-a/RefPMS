"""RefPMS 도메인 데이터 스키마 — Single Source of Truth (SSOT).

각 시트(또는 데이터 그룹)의 필드 정의를 한 곳에 모아 코드 전반의 정합을
보장한다. 다른 모듈은 이 스키마만 참조해 헤더 이름, 필수 여부, 검증 규칙 등을
얻는다.

메타스키마(필드를 정의할 때 살펴볼 9개 측면):
    1. 의미 (meaning)              — 도메인에서 이 필드가 표현하는 것
    2. 데이터 타입 (data_type)     — 문자열 / 숫자 / enum 등
    3. 필수 여부 (required)        — 비어 있으면 에러인지
    4. 형식 제약 (format_constraint) — 정규식·allowlist·길이 제한 등
    5. 중복 (unique)               — 한 프로젝트 내 unique 강제 여부
    6. 다른 필드와의 관계 (relations) — FK / 종속 / 정합 검사
    7. 검증 위치 (validation_location) — 코드의 어느 함수가 검사
    8. 사용자 입력 방법 (input_method) — text entry / combo / auto-filled 등
    9. 단위 (unit)                 — 숫자 필드의 단위 (있을 때만)

특정 항목이 그 필드에 의미 없으면 ``None`` 또는 빈 컬렉션으로 둔다 (N/A).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class FieldDefinition:
    """한 필드의 정의 — 메타스키마 9개 항목."""

    name: str
    meaning: str
    data_type: str
    required: bool
    format_constraint: Optional[str] = None
    unique: Optional[bool] = None
    relations: list[str] = field(default_factory=list)
    validation_location: Optional[str] = None
    input_method: Optional[str] = None
    unit: Optional[str] = None


# ── Pipe_Group ─────────────────────────────────────────────────────────────────

PIPE_GROUP_FIELDS: list[FieldDefinition] = [
    FieldDefinition(
        name="Class_Name",
        meaning=(
            "이 행이 속하는 Class의 이름. Class_Define 시트에서 정의된 Class를"
            " 참조하는 외래 키(FK) 역할."
        ),
        data_type="string",
        required=True,
        format_constraint=None,
        unique=None,  # 한 시트 안에 같은 Class_Name 여러 행이 정상
        relations=["Class_Define.Class_Name (FK)"],
        validation_location=None,  # 별도 검증 없음 (wizard 흐름이 보장)
        input_method="auto-filled (wizard에서 Class 선택 시 자동 채움)",
        unit=None,
    ),
]
