from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from openpyxl import load_workbook

from class_level_model import ClassLevelBundle
from sample_data import build_sample_bundle


@dataclass
class GeneratedRun:
    bundle: ClassLevelBundle
    template_path: Path
    output_path: Path
    rows: list[dict[str, object]]


@pytest.fixture
def sample_bundle():
    return build_sample_bundle()


@pytest.fixture(scope="session")
def generated(tmp_path_factory) -> GeneratedRun:
    """GUI Export 와 같은 함수로 템플릿을 쓰고 pms_generator 를 한 번 돌린 결과 (세션 공유)."""
    from pms_generator import generate_piping_material_class_data
    from template_generator import DEFAULT_TEMPLATE_FILENAME, generate_class_define_template

    out_dir = tmp_path_factory.mktemp("e2e")
    bundle = build_sample_bundle()
    template_path = generate_class_define_template(
        output_path=out_dir / DEFAULT_TEMPLATE_FILENAME, class_level=bundle
    )
    output_path = generate_piping_material_class_data(
        template_path, output_path=out_dir / "Piping_Material_Class_Data.xlsx"
    )
    ws = load_workbook(output_path, read_only=True).worksheets[0]
    values = list(ws.iter_rows(values_only=True))
    header = values[0]
    rows = [dict(zip(header, r)) for r in values[1:]]
    return GeneratedRun(bundle, Path(template_path), Path(output_path), rows)
