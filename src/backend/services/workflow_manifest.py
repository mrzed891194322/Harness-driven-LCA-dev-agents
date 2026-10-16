"""Structured workflow display manifest (not part of injection / bundle hash)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.core.runtime.capabilities import base_capabilities
from backend.core.workflow.config.loader import load_workflow

ROLE_TITLES = {
    "executor": "执行",
    "reviser": "修订",
    "reviewer": "审查",
}

STAGE_TITLES_MAIN = {
    "01-intake-gate": "准入门禁",
    "02-inventory-extraction": "清单提取",
    "03-dataset-mapping": "数据集映射",
    "04-openlca-reporting": "openLCA 计算与报告",
}

STAGE_SHORT = {
    "01-intake-gate": "01",
    "02-inventory-extraction": "02",
    "03-dataset-mapping": "03",
    "04-openlca-reporting": "04",
}

PHASE_TITLES = {
    "inventory": "清单",
    "mapping": "映射",
    "report": "报告",
}


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
                "title": workflow.display_title or name,
                "mode": workflow.display_mode or workflow.workflow_id,
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
        lca = stage.context.get("lca") if isinstance(stage.context.get("lca"), dict) else {}
        phase = str(lca.get("phase") or "") if lca else ""
        stages.append(
            {
                "id": stage.stage_id,
                "title": stage.display_title
                or STAGE_TITLES_MAIN.get(stage.stage_id, stage.stage_id),
                "short_title": stage.display_short_title
                or STAGE_SHORT.get(stage.stage_id, stage.stage_id),
                "resumable": stage.resumable
                or stage.stage_id.startswith("02")
                or stage.stage_id.startswith("03")
                or stage.stage_id.startswith("04"),
                "phase_title": stage.phase_title or PHASE_TITLES.get(phase, ""),
                "assignments": [
                    {
                        "id": aid,
                        "role": workflow.assignments[aid].role,
                        "title": workflow.assignments[aid].display_title
                        or ROLE_TITLES.get(workflow.assignments[aid].role, workflow.assignments[aid].role),
                    }
                    for aid in stage.steps
                ],
            }
        )
    return {
        "name": workflow_path.stem,
        "title": workflow.display_title,
        "mode": workflow.display_mode or workflow.workflow_id,
        "plan": workflow.plan_path,
        "stages": stages,
    }
