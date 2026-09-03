"""Thin manifest.json for an LCA run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ALLOWED_STATUS = frozenset({"running", "failed", "completed"})


def manifest_path(project_root: Path) -> Path:
    return project_root / "workspace" / "memory" / "manifest.json"


def write_manifest(
    project_root: Path,
    *,
    status: str,
    current_stage: str | None,
    status_reason: str | None,
) -> None:
    if status not in ALLOWED_STATUS:
        raise ValueError(f"invalid manifest status: {status}")
    if status in {"failed", "completed"} and not (status_reason or "").strip():
        raise ValueError("terminal manifest needs status_reason")
    path = manifest_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "status": status,
        "current_stage": current_stage,
        "status_reason": status_reason,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
