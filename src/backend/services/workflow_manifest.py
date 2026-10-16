"""Structured workflow display manifest (not part of injection / bundle hash)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.runtime.capabilities import base_capabilities
from backend.core.workflow.config.loader import load_workflow


def list_workflows(project_root: Path, workflows_dir: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(workflows_dir.glob("*.yaml")):
        workflow = load_workflow(
            path, project_root=project_root, capabilities=base_capabilities()
        )
        name = path.stem
        items.append(
            {
                "name": name,
                "id": workflow.workflow_id,
                "title": workflow.display_title,
                "mode": workflow.display_mode,
                "file": str(path.relative_to(project_root)),
            }
        )
    return items


def workflow_manifest(
    project_root: Path, workflow_path: Path
) -> dict[str, Any]:
    workflow = load_workflow(
        workflow_path, project_root=project_root, capabilities=base_capabilities()
    )
    stages: list[dict[str, Any]] = []
    for stage in workflow.stages:
        stages.append(
            {
                "id": stage.stage_id,
                "title": stage.display_title,
                "short_title": stage.display_short_title,
                "resumable": stage.resumable,
                "phase_title": stage.phase_title,
                "assignments": [
                    {
                        "id": aid,
                        "role": workflow.assignments[aid].role,
                        "title": workflow.assignments[aid].display_title,
                    }
                    for aid in stage.steps
                ],
            }
        )
    return {
        "name": workflow_path.stem,
        "id": workflow.workflow_id,
        "title": workflow.display_title,
        "mode": workflow.display_mode,
        "plan": workflow.plan_path,
        "stages": stages,
    }
