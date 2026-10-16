"""Read-only composed injection preview for the harness panel."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from backend.core.agents import injection, spec_mcp as spec_mcp_host
from backend.core.runtime.capabilities import base_capabilities
from backend.core.runtime.launch_spec import build_session_launch_spec
from backend.core.workflow.config.compose import ComposeError
from backend.core.workflow.config.loader import load_workflow


class InjectionViewError(ValueError):
    def __init__(self, errors: list[dict[str, str]]) -> None:
        super().__init__(errors[0]["message"] if errors else "injection view error")
        self.errors = errors


def _workflow_path(project_root: Path, workflow_name: str) -> Path:
    path = project_root / "harness" / "workflows" / f"{workflow_name}.yaml"
    if not path.is_file():
        path = project_root / ".local" / "harness" / "workflows" / f"{workflow_name}.yaml"
    if not path.is_file():
        raise InjectionViewError(
            [{"code": "E-WORKFLOW-MISSING", "message": f"workflow {workflow_name} not found"}]
        )
    return path


def build_injection_view(
    *,
    project_root: Path,
    workflow_name: str,
    stage_id: str | None = None,
    assignment_id: str | None = None,
) -> dict[str, Any]:
    path = _workflow_path(project_root, workflow_name)
    try:
        workflow = load_workflow(
            path, project_root=project_root, capabilities=base_capabilities()
        )
    except (ValueError, ComposeError) as exc:
        code = getattr(exc, "code", "E-WORKFLOW-INVALID")
        raise InjectionViewError([{"code": str(code), "message": str(exc)}]) from exc

    if not assignment_id:
        nodes: list[dict[str, Any]] = []
        for stage in workflow.stages:
            if stage_id and stage.stage_id != stage_id:
                continue
            for aid in stage.steps:
                nodes.append(
                    {
                        "stage_id": stage.stage_id,
                        "assignment_id": aid,
                        "role": workflow.assignments[aid].role,
                    }
                )
        return {"workflow": workflow_name, "nodes": nodes}

    bundle = workflow.bundles.get(assignment_id)
    if bundle is None or (stage_id and bundle.stage_id != stage_id):
        raise InjectionViewError(
            [
                {
                    "code": "E-ASSIGNMENT-MISSING",
                    "message": f"assignment {assignment_id!r} not in workflow",
                }
            ]
        )

    locked = set(workflow.locked_rules)
    locked.update(workflow.locked_rules_by_role.get(bundle.role) or [])

    with tempfile.TemporaryDirectory(prefix="injection-preview-") as tmp:
        workspace = Path(tmp) / "workspace"
        workspace.mkdir()
        key = Path(tmp) / "spec_mcp.key"
        key.write_bytes(b"k" * 64)
        stage = workflow.stage_by_id(bundle.stage_id)
        assignment = workflow.assignments[assignment_id]
        original_ensure = spec_mcp_host.ensure_key
        spec_mcp_host.ensure_key = lambda _root: key  # type: ignore[method-assign]
        try:
            launch = build_session_launch_spec(
                workflow,
                bundle,
                project_root=project_root,
                workspace_root=workspace,
                worker="pi",
                model="default",
                stage=stage,
                assignment=assignment,
                run_id="preview",
                attempt=1,
                session_key="preview",
                run_context={"run_id": "preview"},
            )
        finally:
            spec_mcp_host.ensure_key = original_ensure
        planned = injection.build_intended(launch)

    def rows(component: str, ids: list[str]) -> list[dict[str, Any]]:
        prov = bundle.component_provenance.get(component) or {}
        removed = set()
        out: list[dict[str, Any]] = []
        for rid in ids:
            out.append(
                {
                    "id": rid,
                    "layer": prov.get(rid, "core"),
                    "locked": rid in locked,
                    "removed": False,
                }
            )
        return out

    return {
        "workflow": workflow_name,
        "stage_id": bundle.stage_id,
        "assignment_id": assignment_id,
        "rules": rows("rules", bundle.rule_ids),
        "mcp": rows("mcp", bundle.mcp_tool_ids),
        "knowledge": rows("knowledge", bundle.knowledge_ids),
        "permissions": planned.get("permissions") or {},
        "planned": planned,
        "compose_notes": list(bundle.compose_notes),
    }


def injection_view_http_errors(exc: InjectionViewError) -> HTTPException:
    from fastapi import HTTPException

    return HTTPException(status_code=422, detail={"errors": exc.errors})
