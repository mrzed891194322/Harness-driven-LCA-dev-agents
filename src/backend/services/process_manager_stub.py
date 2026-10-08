from __future__ import annotations

import subprocess
from typing import Any

_active: subprocess.Popen[Any] | None = None
_stop = False


def set_active_process(proc: subprocess.Popen[Any]) -> None:
    global _active
    _active = proc


def clear_active_process() -> None:
    global _active
    _active = None


def should_stop() -> bool:
    return _stop
