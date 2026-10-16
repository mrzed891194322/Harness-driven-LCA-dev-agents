"""Byte-stable golden fingerprints for injection across all workflow assignments."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import PROJECT_ROOT, ensure_harness_plan_files
from tests.t_core.injection.golden_export import (
    GOLDEN_DIR,
    compare_records_to_golden,
    export_all,
    golden_filename,
    load_golden_file,
    write_golden_files,
)

EXPECTED_ASSIGNMENT_COUNT = 14


@pytest.fixture
def golden_injection_env(tmp_path: Path) -> tuple[Path, Path, Path]:
    ensure_harness_plan_files(PROJECT_ROOT)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    key = tmp_path / "spec_mcp.key"
    key.write_bytes(b"k" * 64)
    return PROJECT_ROOT, workspace, key


def test_golden_assignment_count(golden_injection_env: tuple[Path, Path, Path]) -> None:
    project_root, workspace, key = golden_injection_env
    records = export_all(project_root=project_root, workspace_root=workspace, spec_mcp_key=key)
    assert len(records) == EXPECTED_ASSIGNMENT_COUNT
    assert len({(r["workflow"], r["assignment_id"]) for r in records}) == EXPECTED_ASSIGNMENT_COUNT


def test_golden_injection_byte_identical(golden_injection_env: tuple[Path, Path, Path]) -> None:
    project_root, workspace, key = golden_injection_env
    records = export_all(project_root=project_root, workspace_root=workspace, spec_mcp_key=key)
    assert len(records) == EXPECTED_ASSIGNMENT_COUNT
    golden_files = sorted(GOLDEN_DIR.glob("*.json"))
    assert len(golden_files) == EXPECTED_ASSIGNMENT_COUNT
    for record in records:
        name = golden_filename(record["workflow"], record["assignment_id"])
        golden_path = GOLDEN_DIR / name
        assert golden_path.is_file(), f"missing golden {name}"
        golden = load_golden_file(golden_path)
        diffs = compare_records_to_golden(record, golden, project_root=project_root)
        assert not diffs, f"{name}: " + "; ".join(diffs)
