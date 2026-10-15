"""Orchestrator liveness heartbeat (cheap, best-effort)."""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from backend.core.runtime.tool_runtime import write_json_atomic
from backend.settings import records_root

DEFAULT_INTERVAL_SEC = 15.0
DEFAULT_STALE_SEC = 120.0
HEARTBEAT_NAME = "orchestrator.heartbeat.json"


def heartbeat_path(workspace_root: Path) -> Path:
    return records_root(workspace_root) / HEARTBEAT_NAME


def heartbeat_interval_sec() -> float:
    raw = os.getenv("HARNESS_ORCHESTRATOR_HEARTBEAT_SEC", "").strip()
    if not raw:
        return DEFAULT_INTERVAL_SEC
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_INTERVAL_SEC
    return max(1.0, value)


def heartbeat_stale_sec() -> float:
    raw = os.getenv("HARNESS_ORCHESTRATOR_STALE_SEC", "").strip()
    if not raw:
        return DEFAULT_STALE_SEC
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_STALE_SEC
    return max(5.0, value)


def write_heartbeat(workspace_root: Path, *, run_id: str, pid: int | None = None) -> None:
    payload = {
        "pid": int(pid if pid is not None else os.getpid()),
        "run_id": run_id,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    path = heartbeat_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, payload)


def read_heartbeat(workspace_root: Path) -> dict[str, object] | None:
    path = heartbeat_path(workspace_root)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def clear_heartbeat(workspace_root: Path) -> None:
    path = heartbeat_path(workspace_root)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


class OrchestratorHeartbeat:
    """Background writer; never raises to the orchestrator thread."""

    def __init__(self, workspace_root: Path, run_id: str) -> None:
        self._workspace_root = workspace_root
        self._run_id = run_id
        self._interval = heartbeat_interval_sec()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        try:
            write_heartbeat(self._workspace_root, run_id=self._run_id)
        except OSError:
            pass
        self._thread = threading.Thread(target=self._loop, name="orchestrator-heartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=self._interval + 2.0)

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                write_heartbeat(self._workspace_root, run_id=self._run_id)
            except OSError:
                pass


@contextmanager
def orchestrator_heartbeat(workspace_root: Path, run_id: str) -> Iterator[None]:
    beat = OrchestratorHeartbeat(workspace_root, run_id)
    beat.start()
    try:
        yield
    finally:
        beat.stop()


def heartbeat_age_sec(payload: dict[str, object]) -> float | None:
    ts = str(payload.get("ts") or "").strip()
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        seen = datetime.fromisoformat(ts)
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return max(0.0, (datetime.now(timezone.utc) - seen).total_seconds())
