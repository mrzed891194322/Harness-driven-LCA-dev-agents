"""Ensure repository ``src/`` and root are importable without an installed package."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_import_roots(start: Path | None = None) -> Path:
    """Insert ``src`` and project root onto ``sys.path``; return project root."""
    current = (start or Path(__file__)).resolve()
    project_root = next(
        parent for parent in [current, *current.parents] if (parent / "pyproject.toml").is_file()
    )
    src_root = project_root / "src"
    for root in (src_root, project_root):
        text = str(root)
        if text not in sys.path:
            sys.path.insert(0, text)
    return project_root
