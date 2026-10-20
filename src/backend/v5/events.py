"""Structured run log: every state change goes to runs/_run/events.jsonl and the python logger."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("harness.v5")


class EventLog:
    def __init__(self, workspace: Path) -> None:
        self.path = workspace / "runs" / "_run" / "events.jsonl"

    def emit(self, kind: str, **fields: Any) -> dict[str, Any]:
        record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "kind": kind, **fields}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        log.info("%s %s", kind, json.dumps(fields, ensure_ascii=False)[:500])
        return record

    def read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
