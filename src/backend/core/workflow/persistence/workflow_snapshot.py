"""Persist the workflow YAML text used when a run starts."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from backend.core.agents.injection import runs_root
from backend.core.workflow.persistence.manifest import patch_manifest
from backend.settings import run_root

WORKFLOW_SNAPSHOT_NAME = "workflow.yaml"


def evidence_workflow_path(workspace_root: Path, run_id: str) -> Path:
    return run_root(workspace_root) / "evidence" / run_id / WORKFLOW_SNAPSHOT_NAME


def local_workflow_path(project_root: Path, run_id: str) -> Path:
    return runs_root(project_root) / run_id / WORKFLOW_SNAPSHOT_NAME


def write_workflow_snapshot(
    *,
    workspace_root: Path,
    project_root: Path,
    run_id: str,
    workflow_text: str,
) -> str:
    """Write identical workflow YAML to workspace evidence and ``.local/runs``."""
    evidence = evidence_workflow_path(workspace_root, run_id)
    for path in (
        evidence,
        local_workflow_path(project_root, run_id),
    ):
        _write_text_atomic(path, workflow_text)
    rel = evidence.relative_to(workspace_root).as_posix()
    patch_manifest(workspace_root, workflow_snapshot=rel)
    return rel


def read_workflow_snapshot_text(
    project_root: Path, workspace_root: Path, run_id: str
) -> str | None:
    for path in (
        evidence_workflow_path(workspace_root, run_id),
        local_workflow_path(project_root, run_id),
    ):
        if path.is_file():
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                continue
    return None


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            if text and not text.endswith("\n"):
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
