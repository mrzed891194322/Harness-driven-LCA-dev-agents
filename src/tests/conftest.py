"""Shared path constants for the test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
GUI_ROOT = SRC_ROOT / "gui"
WORKFLOWS = PROJECT_ROOT / "harness"

MAIN_PLAN_PATH = PROJECT_ROOT / "harness" / "knowledge" / "plan" / "main_plan.md"
REVISE_PLAN_PATH = PROJECT_ROOT / "harness" / "knowledge" / "plan" / "revise_plan.md"


def ensure_harness_plan_files(project_root: Path = PROJECT_ROOT) -> None:
    """Minimal plan files for orchestrator tests (project-relative spec inputs)."""
    plan_dir = project_root / "harness" / "knowledge" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    main = plan_dir / "main_plan.md"
    if not main.is_file() or main.stat().st_size == 0:
        main.write_text("# plan\n功能单位\n", encoding="utf-8")
    revise = plan_dir / "revise_plan.md"
    if not revise.is_file():
        revise.write_text("# revise\n", encoding="utf-8")
    inputs_dir = project_root / "harness" / "knowledge" / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)


@pytest.fixture(autouse=True)
def _ensure_harness_plan_files_for_tests() -> None:
    ensure_harness_plan_files()
