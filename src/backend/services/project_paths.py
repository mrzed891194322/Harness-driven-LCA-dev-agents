from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
BACKEND_ROOT = PROJECT_ROOT / "src" / "backend"
WORKFLOWS_ROOT = BACKEND_ROOT / "workflows"
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"

MAIN_WORKFLOW_REL = "src/backend/workflows/LCA-main.yaml"
REVISE_WORKFLOW_REL = "src/backend/workflows/LCA-revise.yaml"
HARNESS_WORKFLOW_DOC_PREFIX = "workflows/"
