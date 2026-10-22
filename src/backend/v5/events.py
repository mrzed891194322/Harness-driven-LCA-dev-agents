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
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("harness.v5")
TEXT_LIMIT = 4000


def _last_seq(handle) -> int:
    size = handle.seek(0, os.SEEK_END)
    if not size:
        return 0
    handle.seek(max(0, size - 65536))
    for line in reversed(handle.read().splitlines()):
        try:
            return int(json.loads(line).get("seq") or 0)
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
        with self.path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                record = {"seq": _last_seq(handle) + 1, "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "kind": kind,
                          **self.context, **fields}
                handle.seek(0, os.SEEK_END)
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
        log.info("%s %s", kind, json.dumps(fields, ensure_ascii=False)[:500])
        return record

    def read(self, after_seq: int = 0) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if int(rec.get("seq") or 0) > after_seq:
                out.append(rec)
        return out
