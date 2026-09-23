"""체크리스트 2-5: 카탈로그(domain_schema)에서 파생된 목록이 실제로 일치하는지 + schema_audit."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import domain_schema
from class_level_model import CLASS_DEFINE_REQUIRED_FIELDS
from units_notation_headers import CLASS_DEFINE_STORAGE_KEYS

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_class_define_storage_keys_follow_catalog():
    assert list(CLASS_DEFINE_STORAGE_KEYS) == [f.name for f in domain_schema.CLASS_DEFINE_FIELDS]


def test_class_define_required_fields_follow_catalog():
    # Class_Name 은 validate() 가 따로 검사하므로 필수 목록에서 제외된다.
    expected = [f.name for f in domain_schema.CLASS_DEFINE_FIELDS if f.required and f.name != "Class_Name"]
    assert list(CLASS_DEFINE_REQUIRED_FIELDS) == expected


def test_schema_audit_reports_no_issues():
    result = subprocess.run(
        [sys.executable, "tools/schema_audit.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    # schema_audit 는 이슈가 하나라도 있으면 종료 코드 1.
    assert result.returncode == 0, result.stdout + result.stderr
