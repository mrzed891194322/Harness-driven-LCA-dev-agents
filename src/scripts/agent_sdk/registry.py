"""Load provider modules by worker name."""

from __future__ import annotations

import importlib

from .runtime import WorkerError

NAMES = ("claude", "codex", "opencode", "dsh", "antigravity")


def load(name: str):
    key = (name or "").strip().lower()
    if key not in NAMES:
        raise WorkerError(f"unsupported worker: {name}")
    return importlib.import_module(f"{__package__}.providers.{key}")
