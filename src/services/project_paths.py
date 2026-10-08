from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
SRC_ROOT = PROJECT_ROOT / "src"
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"
