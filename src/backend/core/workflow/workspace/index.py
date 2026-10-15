"""Host-owned attempt registration and publication after deterministic acceptance."""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.runtime.tool_runtime import write_json_atomic

from .layout import (
    accepted,
    attempt_dir,
    inside,
    resolve_path,
    writer_dir,
)

_WRITER_ROLES = frozenset({"executor", "reviser"})
_STAGE_04 = "04-openlca-reporting"


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _attempts_path(workspace: Path, stage: str) -> Path:
    return workspace / "runs" / stage / "attempts.json"


def _load_attempts_document(workspace: Path, stage: str) -> dict[str, Any]:
    path = _attempts_path(workspace, stage)
    if not path.is_file():
        return {"stage": stage, "attempts": []}
    import json

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"stage": stage, "attempts": []}
    if isinstance(raw, list):
        rows = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            rel = str(row.get("dir") or row.get("path") or "").strip()
            if not rel and row.get("role") and row.get("attempt"):
                rel = f"runs/{stage}/{row['role']}-{row['attempt']}"
            rows.append(
                {
                    "dir": rel,
                    "role": row.get("role"),
                    "attempt": row.get("attempt"),
                    "origin": row.get("origin") or "whole-lca",
                    "started_at": row.get("started_at"),
                    "ended_at": row.get("ended_at"),
                    "status": row.get("status"),
                    "verdict": row.get("verdict"),
                    "reviews": row.get("reviews"),
                    "openlca_deleted": row.get("openlca_deleted"),
                    "openlca_skipped": row.get("openlca_skipped"),
                }
            )
        return {"stage": stage, "attempts": rows}
    if isinstance(raw, dict):
        items = raw.get("attempts")
        if not isinstance(items, list):
            items = []
        return {
            "stage": str(raw.get("stage") or stage),
            "attempts": [r for r in items if isinstance(r, dict)],
        }
    return {"stage": stage, "attempts": []}


def _save_attempts_document(workspace: Path, stage: str, document: dict[str, Any]) -> None:
    payload = {
        "stage": document.get("stage") or stage,
        "attempts": document.get("attempts") or [],
    }
    write_json_atomic(_attempts_path(workspace, stage), payload)


def register_attempt(
    workspace: Path,
    stage: str,
    role: str,
    attempt: int,
    run_id: str,
    *,
    origin: str = "whole-lca",
) -> None:
    del run_id  # run identity lives under .local/runs, not workspace attempts.json
    directory = attempt_dir(workspace, stage, role, attempt)
    directory.mkdir(parents=True, exist_ok=True)
    document = _load_attempts_document(workspace, stage)
    rows: list[dict[str, Any]] = list(document.get("attempts") or [])
    rel_dir = directory.relative_to(workspace.resolve()).as_posix()
    existing = next(
        (r for r in rows if r.get("role") == role and int(r.get("attempt") or 0) == attempt),
        None,
    )
    if not existing:
        rows.append(
            {
                "dir": rel_dir,
                "role": role,
                "attempt": attempt,
                "origin": origin,
                "started_at": _utc_now(),
                "ended_at": None,
                "status": "running",
                "verdict": None,
            }
        )
    else:
        existing.setdefault("dir", rel_dir)
        existing.setdefault("origin", origin)
        existing.setdefault("started_at", _utc_now())
        existing.setdefault("status", "running")
    document["attempts"] = rows
    _save_attempts_document(workspace, stage, document)


def should_run_openlca_attempt_cleanup(
    workspace: Path,
    stage_id: str,
    *,
    role: str,
    attempt: int,
) -> bool:
    if stage_id != _STAGE_04 or role not in _WRITER_ROLES:
        return False
    if attempt < 2:
        return False
    document = _load_attempts_document(workspace, stage_id)
    row = next(
        (
            r
            for r in document.get("attempts") or []
            if r.get("role") == role and int(r.get("attempt") or 0) == attempt
        ),
        None,
    )
    if row is None:
        return True
    return row.get("openlca_deleted") is None and row.get("openlca_skipped") is None


def record_openlca_cleanup(
    workspace: Path,
    stage_id: str,
    *,
    role: str,
    attempt: int,
    deleted: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
) -> None:
    document = _load_attempts_document(workspace, stage_id)
    rows: list[dict[str, Any]] = list(document.get("attempts") or [])
    row = next(
        (
            r
            for r in rows
            if r.get("role") == role and int(r.get("attempt") or 0) == attempt
        ),
        None,
    )
    if row is None:
        rel = f"runs/{stage_id}/{role}-{attempt}"
        row = {
            "dir": rel,
            "role": role,
            "attempt": attempt,
            "origin": "whole-lca",
            "started_at": _utc_now(),
            "status": "running",
        }
        rows.append(row)
    row["openlca_deleted"] = deleted
    row["openlca_skipped"] = skipped
    document["attempts"] = rows
    _save_attempts_document(workspace, stage_id, document)


def accept_stage(
    workspace: Path,
    project: Path,
    spec,
    reviewer_attempt: int,
    run_id: str,
) -> dict:
    writer = writer_dir(workspace, spec.spec_id, reviewer_attempt)
    paths: dict[str, str] = {}
    fingerprints: dict[str, str] = {}
    for item in spec.outputs:
        if item.artifact_kind != "deliverable":
            continue
        source = resolve_path(
            workspace,
            project,
            spec.spec_id,
            item.path,
            role=None,
            attempt=reviewer_attempt,
        )
        if not source.exists() and item.required:
            raise ValueError(f"missing accepted deliverable: {item.path}")
        if not source.exists():
            continue
        if item.path.startswith("workspace/"):
            relative = item.path.removeprefix("workspace/")
        else:
            relative = item.path
        target = inside(workspace, f"artifacts/{relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            for child in source.rglob("*"):
                if child.is_symlink():
                    raise ValueError(f"symlink in deliverable: {child}")
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
        paths[item.path] = source.relative_to(workspace.resolve()).as_posix()
        for file in sorted(source.rglob("*")) if source.is_dir() else [source]:
            if not file.is_file():
                continue
            fingerprints[file.relative_to(workspace.resolve()).as_posix()] = (
                hashlib.sha256(file.read_bytes()).hexdigest()
            )

    digest_parts = [fingerprints[k] for k in sorted(fingerprints)]
    fingerprint = hashlib.sha256("".join(digest_parts).encode()).hexdigest()
    writer_rel = writer.relative_to(workspace.resolve()).as_posix()
    reviewer_rel = (
        attempt_dir(workspace, spec.spec_id, "reviewer", reviewer_attempt)
        .relative_to(workspace.resolve())
        .as_posix()
    )
    previous = accepted(workspace, spec.spec_id)
    entry = {
        **previous,
        "stage": spec.spec_id,
        "run_id": run_id,
        "executor": writer_rel,
        "writer": writer_rel,
        "reviewer": reviewer_rel,
        "accepted_at": _utc_now(),
        "fingerprint": fingerprint,
        "deliverables": paths,
        "fingerprints": fingerprints,
    }
    write_json_atomic(
        workspace / "runs" / spec.spec_id / "accepted.json",
        entry,
    )
    return entry
