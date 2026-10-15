"""GUI-facing run summary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.runtime.tool_runtime import write_json_atomic
from backend.settings import run_root


def manifest_path(workspace_root: Path) -> Path:
    return run_root(workspace_root) / "manifest.json"


def write_manifest(
    workspace_root: Path,
    *,
    status: str,
    current_stage: str | None,
    status_reason: str | None,
    run_id: str,
    attempt: int | None = None,
    resumed_from: str | None = None,
    resume_from_stage: str | None = None,
) -> None:
    path = manifest_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "status": status,
        "current_stage": current_stage,
        "status_reason": status_reason,
        "run_id": run_id,
    }
    if isinstance(attempt, int):
        payload["attempt"] = attempt
    if resumed_from:
        payload["resumed_from"] = resumed_from
    if resume_from_stage:
        payload["resume_from_stage"] = resume_from_stage
    write_json_atomic(path, payload)
