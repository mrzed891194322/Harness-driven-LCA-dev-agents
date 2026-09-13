"""Bind YAML assignment materials into a backend-agnostic SessionConfig."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.agent_sdk.mcp import mcp_servers_for_tools
from scripts.agent_sdk.models import load_worker_model
from scripts.agent_sdk.session import SessionConfig

from .assemble import assignment_spec_paths
from .loader import assignment_rule_ids
from .models import Assignment, Stage, Workflow

LCA_ENV_TOOLS = ("control_openlca", "lca_artifacts")


def build_session_config(
    workflow: Workflow,
    *,
    project_root: Path,
    workspace_root: Path,
    worker: str,
    stage: Stage,
    assignment: Assignment,
    run_id: str,
    attempt: int,
) -> SessionConfig:
    """Fill SessionConfig from YAML. Providers must not parse the workflow."""
    tool_ids = list(assignment.tools)
    mcp_servers = mcp_servers_for_tools(
        tool_ids,
        {tool_id: spec.to_mcp_dict() for tool_id, spec in workflow.tools.items()},
    )
    extra_env = {
        "LCA_RUN_ID": run_id,
        "LCA_STAGE": stage.stage_id,
        "LCA_ATTEMPT": str(attempt),
        "LCA_ROLE": assignment.role,
        "LCA_WORKSPACE": str(workspace_root),
    }
    for tool_id in tool_ids:
        if tool_id not in LCA_ENV_TOOLS:
            continue
        server = mcp_servers[tool_id]
        merged: dict[str, Any] = {**server.get("env", {}), **extra_env}
        server["env"] = merged
    return SessionConfig(
        worker=worker,
        cwd=project_root,
        tmp_dir=workspace_root / "tmp",
        mcp_servers=mcp_servers,
        model=load_worker_model(worker, project_root),
        spec_paths=assignment_spec_paths(workflow, stage, assignment),
        rule_ids=assignment_rule_ids(workflow, assignment),
        tool_ids=tool_ids,
        stage_id=stage.stage_id,
        role=assignment.role,
        attempt=attempt,
    )
