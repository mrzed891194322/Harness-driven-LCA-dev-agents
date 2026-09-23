"""Project-local UV_CACHE_DIR helpers."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_UV_CACHE_REL = ".uv-cache"


def resolve_uv_cache_dir(project_root: Path) -> Path:
    """Return absolute UV cache dir under project root by default."""
    raw = (os.environ.get("UV_CACHE_DIR") or "").strip().strip('"').strip("'")
    if raw:
        path = Path(raw)
        if not path.is_absolute():
            path = project_root / path
    else:
        path = project_root / DEFAULT_UV_CACHE_REL
    return path.resolve()


def ensure_uv_cache_dir(project_root: Path) -> Path:
    """Create and export UV_CACHE_DIR for this process and child MCP servers."""
    path = resolve_uv_cache_dir(project_root)
    path.mkdir(parents=True, exist_ok=True)
    os.environ["UV_CACHE_DIR"] = str(path)
    return path
