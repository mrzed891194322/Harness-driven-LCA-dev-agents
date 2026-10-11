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


def clear_stop() -> None:
    global _stop
    _stop = False


def request_stop() -> bool:
    """Ask the active command to stop. Only that process is signalled."""
    global _stop
    _stop = True
    proc = _active
    if proc is None or proc.poll() is not None:
        return False
    try:
        proc.terminate()
    except ProcessLookupError:
        return False
    return True
