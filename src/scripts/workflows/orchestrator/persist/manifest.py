"""GUI-facing run summary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.workflows.runtime.tool_runtime import write_json_atomic


def manifest_path(workspace_root: Path) -> Path:
    return workspace_root / "memory" / "manifest.json"


def write_manifest(
    workspace_root: Path,
    *,
    status: str,
    current_stage: str | None,
    status_reason: str | None,
    run_id: str,
) -> None:
    path = manifest_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "status": status,
        "current_stage": current_stage,
        "status_reason": status_reason,
        "run_id": run_id,
    }
    write_json_atomic(path, payload)
