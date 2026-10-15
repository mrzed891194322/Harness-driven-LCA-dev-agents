"""Shared path constants for the test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "src" / "backend"
FRONTEND_ROOT = PROJECT_ROOT / "src" / "frontend"
WEB_ROOT = FRONTEND_ROOT / "web"
WORKFLOWS = PROJECT_ROOT / "src" / "backend" / "workflows"

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


@pytest.fixture(autouse=True)
def _isolate_orchestrator_hooks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must not install the production openLCA cleanup hook or connect_ipc."""
    from backend.core.workflow.hooks import set_before_openlca_write

    set_before_openlca_write(None)

    def _forbid_connect_ipc(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("tests must not call connect_ipc (use a fake client)")

    monkeypatch.setattr(
        "backend.services.openlca_attempt_cleanup.connect_ipc",
        _forbid_connect_ipc,
    )
    yield
    set_before_openlca_write(None)
