"""Generic harness identifiers and relative-path safety."""

from __future__ import annotations

import re

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
