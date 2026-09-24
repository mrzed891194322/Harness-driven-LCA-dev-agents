"""Tool-local relative path safety (no core imports)."""

from __future__ import annotations


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
