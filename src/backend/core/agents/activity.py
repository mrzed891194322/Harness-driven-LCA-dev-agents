"""Structured worker activity log (one JSON object per line) for the run UI.

Lives under ``.local/runs/<run_id>/events.jsonl`` because whole-lca preclean
wipes ``workspace/records`` and ``workspace/tmp``.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any

ACTIVITY_FILE = "events.jsonl"
MAX_READ_BYTES = 512 * 1024
_RUN_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_lock = threading.Lock()


def activity_log_path(project_root: Path, run_id: str) -> Path:
    if not _RUN_ID.match(run_id or "") or run_id in {".", ".."}:
        raise ValueError(f"invalid run_id: {run_id!r}")
    return project_root / ".local" / "runs" / run_id / ACTIVITY_FILE


def append_activity(path: Path, record: dict[str, Any]) -> None:
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def read_activity(path: Path, offset: int = 0) -> dict[str, Any]:
    """Return complete lines after byte ``offset`` and the next offset.

    A partially written trailing line is left for the next read. ``reset`` is
    true when the offset no longer fits the file (rotated / new run).
    """
    if not path.is_file():
        return {"events": [], "offsets": [], "offset": 0, "reset": offset != 0}
    size = path.stat().st_size
    reset = offset < 0 or offset > size
    start = 0 if reset else offset
    with path.open("rb") as handle:
        handle.seek(start)
        data = handle.read(MAX_READ_BYTES)
    end = data.rfind(b"\n")
    if end < 0:
        return {"events": [], "offsets": [], "offset": start, "reset": reset}
    events: list[dict[str, Any]] = []
    offsets: list[int] = []  # byte offset just past each event's line (resume point)
    pos = start
    for raw in data[: end + 1].splitlines(keepends=True):
        pos += len(raw)
        try:
            item = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
            offsets.append(pos)
    return {"events": events, "offsets": offsets, "offset": start + end + 1, "reset": reset}
