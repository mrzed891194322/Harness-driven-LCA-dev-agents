"""Structured run log (WORKFLOW_DESIGN §6): runs/_run/events.jsonl, one record per line.

Common fields: ``seq`` (monotonic per file, assigned under a file lock), ``ts``, ``kind`` and the
context the caller passes (``run_id``, ``node``, ``rev``, ``agent``, ``attempt``, ``step``). The GUI
activity stream reads these records directly (``/api/workflow/progress?after_seq=``).
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("harness.v5")
TEXT_LIMIT = 4000


TAIL_BYTES = 65536
# Per-file seq counter of this process: path -> (last seq, inode, size after our last write).
# Re-initialised from the file tail when the file was replaced or someone else appended.
_SEQ: dict[str, tuple[int, int, int]] = {}
_SEQ_LOCK = threading.Lock()


def tail_seq(path: Path) -> int:
    """Last ``seq`` in a JSONL file. Binary tail read; the possibly partial first line is skipped."""
    try:
        with path.open("rb") as handle:
            size = handle.seek(0, os.SEEK_END)
            start = max(0, size - TAIL_BYTES)
            handle.seek(start)
            lines = handle.read().split(b"\n")
    except FileNotFoundError:
        return 0
    if start:
        lines = lines[1:]
    for raw in reversed(lines):
        try:
            return int(json.loads(raw.decode("utf-8")).get("seq") or 0)
        except (ValueError, AttributeError):
            continue
    return 0


class EventLog:
    def __init__(self, workspace: Path, **context: Any) -> None:
        self.path = workspace / "runs" / "_run" / "events.jsonl"
        self.context = {k: v for k, v in context.items() if v is not None}

    def bind(self, **context: Any) -> EventLog:
        out = EventLog.__new__(EventLog)
        out.path, out.context = self.path, {**self.context, **{k: v for k, v in context.items() if v is not None}}
        return out

    def emit(self, kind: str, **fields: Any) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        key = str(self.path.resolve())
        with _SEQ_LOCK, self.path.open("ab") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                st = os.fstat(handle.fileno())
                cached = _SEQ.get(key)
                last = cached[0] if cached and cached[1:] == (st.st_ino, st.st_size) else tail_seq(self.path)
                record = {"seq": last + 1, "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "kind": kind,
                          **self.context, **fields}
                handle.write((json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8"))
                handle.flush()
                _SEQ[key] = (record["seq"], st.st_ino, os.fstat(handle.fileno()).st_size)
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
        log.info("%s %s", kind, json.dumps(fields, ensure_ascii=False)[:500])
        return record

    def read(self, after_seq: int = 0) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if int(rec.get("seq") or 0) > after_seq:
                out.append(rec)
        return out
