from __future__ import annotations

from pathlib import Path

from backend.core.workflow.local_workflows import (
    DEFAULT_WORKFLOWS_DIR,
    LOCAL_WORKFLOWS_DIR,
    MAIN_WORKFLOW_NAME,
    REVISE_WORKFLOW_NAME,
    workflow_name_from_task,
)

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
BACKEND_ROOT = PROJECT_ROOT / "src" / "backend"
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"
HARNESS_ROOT = PROJECT_ROOT / "harness"

MAIN_WORKFLOW_REL = f"{DEFAULT_WORKFLOWS_DIR.as_posix()}/{MAIN_WORKFLOW_NAME}"
REVISE_WORKFLOW_REL = f"{DEFAULT_WORKFLOWS_DIR.as_posix()}/{REVISE_WORKFLOW_NAME}"

HARNESS_WORKFLOW_DOC_PREFIX = "workflows/"
