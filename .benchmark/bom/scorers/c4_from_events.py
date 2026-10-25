"""C4 intervention frequency: count reject and redo records in events.jsonl.

Counted kinds match the harness run log (``src/backend/workflow``):

- redo: ``redo_requested``, ``redo_approved``, ``redo_refused`` (any ``redo_`` kind)
- reject: ``submit_rejected``, ``route`` with ``when`` of ``reject`` or
  ``checks_failed``, ``submit`` whose ``verdict`` is ``reject``

``host_checks`` alone is not an intervention. Each event lands in one bucket.
``c4_if`` is ``reject_count + redo_count``. There is no ground-truth file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REJECT_WHEN = {"reject", "checks_failed"}


def classify(event: dict[str, Any]) -> str | None:
    kind = str(event.get("kind") or "")
    if kind == "redo" or kind.startswith("redo_"):
        return "redo"
    if "reject" in kind:
        return "reject"
    if kind == "route" and event.get("when") in _REJECT_WHEN:
        return "reject"
    if kind == "submit" and str(event.get("verdict") or "") == "reject":
        return "reject"
    return None


def score_events(path: Path) -> dict[str, Any]:
    reject_count = 0
    redo_count = 0
    n_events = 0
    skipped = 0
    matches: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    for line_no, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not isinstance(event, dict):
            skipped += 1
            continue
        n_events += 1
        bucket = classify(event)
        if bucket == "reject":
            reject_count += 1
        elif bucket == "redo":
            redo_count += 1
        else:
            continue
        matches.append(
            {
                "line": line_no,
                "seq": event.get("seq"),
                "kind": event.get("kind"),
                "bucket": bucket,
            }
        )
    return {
        "reject_count": reject_count,
        "redo_count": redo_count,
        "c4_if": reject_count + redo_count,
        "n_events": n_events,
        "skipped_lines": skipped,
        "matches": matches,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="统计 events.jsonl 里的 reject / redo")
    parser.add_argument("events", type=Path)
    args = parser.parse_args(argv)
    json.dump(score_events(args.events), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
