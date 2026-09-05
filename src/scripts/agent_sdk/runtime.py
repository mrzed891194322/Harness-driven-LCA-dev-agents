"""Shared runtime helpers for provider runners."""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Callable
from typing import Protocol


class WorkerError(RuntimeError):
    """Worker could not complete the session."""


EmitFn = Callable[[str], None]


class Provider(Protocol):
    NAME: str
    SDK_MODULE: str

    def inspect(self) -> tuple[bool, str]:
        ...

    def run(
        self,
        prompt: str,
        *,
        cwd,
        stop_event=None,
        emit: EmitFn | None = None,
    ) -> None:
        ...


def emit(line: str) -> None:
    sys.stdout.write(line if line.endswith("\n") else line + "\n")
    sys.stdout.flush()


def format_event(*, kind: str, text: str, limit: int = 8000) -> str:
    clipped = text if len(text) <= limit else text[:limit] + "…"
    return f"[{kind}] {clipped}"


def jsonish(value: object) -> str:
    if isinstance(value, (str, int, float)):
        return str(value)
    payload = getattr(value, "payload", None)
    if payload is not None and payload is not value:
        try:
            return json.dumps(
                {"method": getattr(value, "method", None), "payload": payload},
                ensure_ascii=False,
                default=str,
            )
        except TypeError:
            pass
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)


def sdk_importable(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
    except ImportError:
        return False
    return True


def resolve_emit(callback: EmitFn | None) -> EmitFn:
    return callback if callback is not None else emit
