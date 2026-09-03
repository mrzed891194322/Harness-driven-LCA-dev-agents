"""Machine-readable worker handoff files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXECUTOR_STATUS = frozenset({"ok", "failed", "blocked"})
REVIEWER_STATUS = frozenset({"passed", "failed"})


@dataclass(frozen=True)
class Handoff:
    role: str
    stage: str
    attempt: int
    status: str
    status_reason: str
    fix_instructions: tuple[str, ...]
    artifacts: tuple[str, ...]
    path: Path


def handoff_path(project_root: Path, stage: str, role: str, attempt: int) -> Path:
    return (
        project_root
        / "workspace"
        / "memory"
        / "handoffs"
        / f"{stage}-{role}-{attempt}.json"
    )


def review_notes_path(project_root: Path, stage: str, attempt: int) -> Path:
    return project_root / "workspace" / "memory" / "reviews" / f"{stage}-{attempt}.md"


def load_handoff(path: Path, *, expected_role: str, expected_stage: str) -> Handoff:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid handoff JSON: {path}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"handoff is not an object: {path}")
    role = str(raw.get("role") or "")
    stage = str(raw.get("stage") or "")
    status = str(raw.get("status") or "")
    reason = str(raw.get("status_reason") or "").strip()
    if role != expected_role or stage != expected_stage:
        raise ValueError(f"handoff role/stage mismatch in {path}")
    if role == "executor" and status not in EXECUTOR_STATUS:
        raise ValueError(f"invalid executor status {status!r} in {path}")
    if role == "reviewer" and status not in REVIEWER_STATUS:
        raise ValueError(f"invalid reviewer status {status!r} in {path}")
    if not reason:
        raise ValueError(f"handoff missing status_reason: {path}")
    fix_raw = raw.get("fix_instructions") or []
    if isinstance(fix_raw, str):
        fix_items = (fix_raw,) if fix_raw.strip() else ()
    else:
        fix_items = tuple(str(item) for item in fix_raw if str(item).strip())
    if role == "reviewer" and status == "failed" and not fix_items:
        raise ValueError(f"failed reviewer handoff needs fix_instructions: {path}")
    artifacts = tuple(str(item) for item in (raw.get("artifacts") or ()))
    return Handoff(
        role=role,
        stage=stage,
        attempt=int(raw.get("attempt") or 0),
        status=status,
        status_reason=reason,
        fix_instructions=fix_items,
        artifacts=artifacts,
        path=path,
    )


def dump_example_schema() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "role": "reviewer",
        "stage": "02-inventory-extraction",
        "attempt": 1,
        "status": "passed",
        "status_reason": "BOM covers the plan.",
        "fix_instructions": [],
        "artifacts": ["workspace/outputs/inventory/extracted-bom.json"],
    }
