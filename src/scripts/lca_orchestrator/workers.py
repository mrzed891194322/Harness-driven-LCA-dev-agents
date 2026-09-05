"""Worker backends: generic sessions that only receive a prompt."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Protocol

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from agent_sdk import NAMES, WorkerError, emit, format_event, run as sdk_run


class WorkerBackend(Protocol):
    name: str

    def run(self, prompt: str, *, cwd: Path, stop_event: threading.Event | None = None) -> None:
        ...


def get_backend(name: str) -> WorkerBackend:
    key = (name or "").strip().lower()
    if key not in NAMES:
        raise WorkerError(f"unsupported worker: {name}")
    return _SdkWorker(key)


class _SdkWorker:
    def __init__(self, name: str) -> None:
        self.name = name

    def run(
        self,
        prompt: str,
        *,
        cwd: Path,
        stop_event: threading.Event | None = None,
    ) -> None:
        sdk_run(self.name, prompt, cwd=cwd, stop_event=stop_event)


__all__ = [
    "WorkerBackend",
    "WorkerError",
    "emit",
    "format_event",
    "get_backend",
]
