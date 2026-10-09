"""Project-local UV_CACHE_DIR helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

DEFAULT_UV_CACHE_REL = ".uv-cache"


def resolve_uv_cache_dir(
    project_root: Path, env: Mapping[str, str] | None = None
) -> Path:
    """Return the absolute UV cache dir; always inside the project.

    A ``UV_CACHE_DIR`` inherited from the launching shell that points outside the
    project (e.g. a sandbox path under /tmp) must not leak into worker MCP
    configs (ISSUES #16), so it falls back to ``<project>/.uv-cache``.
    """
    root = project_root.resolve()
    source = os.environ if env is None else env
    raw = (source.get("UV_CACHE_DIR") or "").strip().strip('"').strip("'")
    default = root / DEFAULT_UV_CACHE_REL
    if not raw:
        return default
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if not path.is_relative_to(root):
        return default
    return path


def ensure_uv_cache_dir(project_root: Path) -> Path:
    """Create and export UV_CACHE_DIR for this process and child MCP servers."""
    path = resolve_uv_cache_dir(project_root)
    path.mkdir(parents=True, exist_ok=True)
    os.environ["UV_CACHE_DIR"] = str(path)
    return path
