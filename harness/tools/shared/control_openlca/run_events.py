"""Append structured events to ``.local/runs/<run_id>/events.jsonl`` (harness-safe)."""

from __future__ import annotations

import json
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_RUN_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_lock = threading.Lock()


def _valid_run_id(run_id: str) -> bool:
    return bool(run_id) and bool(_RUN_ID.match(run_id)) and run_id not in {".", ".."}


def activity_log_path(project_root: Path, run_id: str) -> Path:
    if not _valid_run_id(run_id):
        raise ValueError(f"invalid run_id: {run_id!r}")
    return project_root / ".local" / "runs" / run_id / "events.jsonl"


def append_run_event(project_root: Path, run_id: str, record: dict[str, Any]) -> None:
    path = activity_log_path(project_root, run_id)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
