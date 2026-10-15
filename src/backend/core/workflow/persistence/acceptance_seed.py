"""Seed evidence manifest acceptance before stage execution (resume-lca)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.core.runtime.tool_runtime import write_json_atomic
from backend.settings import run_root

ACCEPTANCE_MODEL = "lca.model"
MANIFEST_SCHEMA_VERSION = 2


def seed_acceptance_manifest(
    workspace_root: Path,
    new_run_id: str,
    acceptance_blob: dict[str, Any],
) -> Path:
    path = run_root(workspace_root) / "evidence" / new_run_id / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": new_run_id,
        "calls": [],
        "accepted": {ACCEPTANCE_MODEL: acceptance_blob},
    }
    write_json_atomic(path, payload)
    return path


def write_resume_metadata(
    workspace_root: Path,
    run_id: str,
    resumed_from: str,
    from_stage: str,
) -> None:
    payload = {
        "resumed_from": resumed_from,
        "from_stage": from_stage,
        "run_id": run_id,
    }
    path = run_root(workspace_root) / "evidence" / run_id / "resume.json"
    write_json_atomic(path, payload)
