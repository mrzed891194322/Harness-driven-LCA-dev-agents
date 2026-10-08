"""Generic harness identifiers and relative-path safety."""

from __future__ import annotations

import re
from pathlib import Path

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def require_identifier(value: str, *, label: str) -> str:
    text = str(value)
    if not _ID_RE.fullmatch(text):
        raise ValueError(f"invalid {label}: {value!r}")
    return text


def require_relative_path(value: str, *, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} must not be empty")
    if text.startswith("/") or text.startswith("\\"):
        raise ValueError(f"{label} must be a relative path: {value!r}")
    parts = text.replace("\\", "/").split("/")
    if any(part == ".." for part in parts):
        raise ValueError(f"{label} must not contain '..': {value!r}")
    return text


def resolve_project_path(project_root: Path, relative: str, *, label: str) -> Path:
    """Resolve a project-relative path and ensure it stays under project_root."""
    require_relative_path(relative, label=label)
    root = project_root.resolve()
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"{label} escapes project root: {relative!r}")
    return resolved


def require_workspace_output(value: str, *, label: str) -> str:
    """Stage outputs must be workspace-relative (prefix workspace/)."""
    text = require_relative_path(value, label=label)
    normalized = text.replace("\\", "/")
    if not normalized.startswith("workspace/") and normalized != "workspace":
        raise ValueError(f"{label} must start with 'workspace/': {value!r}")
    return text
