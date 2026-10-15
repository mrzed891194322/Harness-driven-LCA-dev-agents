"""Host-owned attempt registration and publication after deterministic acceptance."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from backend.core.runtime.tool_runtime import write_json_atomic

from .layout import (
    accepted,
    attempt_dir,
    attempts,
    inside,
    resolve_path,
    writer_dir,
)


def register_attempt(
    workspace: Path,
    stage: str,
    role: str,
    attempt: int,
    run_id: str,
) -> None:
    directory = attempt_dir(workspace, stage, role, attempt)
    directory.mkdir(parents=True, exist_ok=True)
    rows = attempts(workspace, stage)
    existing = next(
        (r for r in rows if r.get("role") == role and r.get("attempt") == attempt),
        None,
    )
    if existing and existing.get("run_id") != run_id:
        raise ValueError("attempt already belongs to another run")
    if not existing:
        rows.append(
            {
                "role": role,
                "attempt": attempt,
                "run_id": run_id,
                "path": directory.relative_to(workspace.resolve()).as_posix(),
            }
        )
        write_json_atomic(
            workspace / "runs" / stage / "attempts.json",
            rows,
        )


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

    previous = accepted(workspace, spec.spec_id)
    entry = {
        **previous,
        "stage": spec.spec_id,
        "run_id": run_id,
        "writer": writer.relative_to(workspace.resolve()).as_posix(),
        "reviewer": attempt_dir(
            workspace, spec.spec_id, "reviewer", reviewer_attempt
        )
        .relative_to(workspace.resolve())
        .as_posix(),
        "deliverables": paths,
        "fingerprints": fingerprints,
    }
    write_json_atomic(
        workspace / "runs" / spec.spec_id / "accepted.json",
        entry,
    )
    return entry
