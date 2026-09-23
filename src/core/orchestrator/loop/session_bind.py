"""Bind YAML assignment materials into a backend-agnostic SessionConfig."""

from __future__ import annotations

from pathlib import Path

from core.agents.archive import mcp_render_dir, turn_archive_dir
from core.agents.mcp import mcp_servers_for_tools, rewrite_uv_run_python
from core.agents.session import SessionConfig
from core.agents.uv_env import ensure_uv_cache_dir
from core.runtime.context import RunContext
from core.runtime.tool_runtime import (
    apply_tool_runtime,
    mcp_context_path,
    write_context_file,
)

from ..load.bundle import TaskBundle
from ..load.models import Assignment, Stage, Workflow

__all__ = ["build_session_config", "mcp_context_path"]


def build_session_config(
    workflow: Workflow,
    bundle: TaskBundle,
    *,
    project_root: Path,
    workspace_root: Path,
    worker: str,
    model: str,
    stage: Stage,
    assignment: Assignment,
    run_id: str,
    attempt: int,
) -> SessionConfig:
    """Fill SessionConfig from resolved TaskBundle. Providers must not parse YAML."""
    del stage, assignment
    uv_cache = ensure_uv_cache_dir(project_root)
    tool_ids = list(bundle.tool_ids)
    mcp_servers = mcp_servers_for_tools(
        tool_ids,
        {tool_id: spec.to_mcp_dict() for tool_id, spec in workflow.tools.items()},
    )
    run_ctx = RunContext(
        project_root=project_root,
        workspace_root=workspace_root,
        run_id=run_id,
        stage_id=bundle.stage_id,
        assignment_id=bundle.assignment_id,
        attempt=attempt,
        role=bundle.role,
        metadata=dict(bundle.context),
    )
    context_path = None
    if any(
        (spec.runtime and spec.runtime.context_file)
        for tool_id in tool_ids
        for spec in [workflow.tools.get(tool_id)]
        if spec is not None
    ):
        context_path = write_context_file(run_ctx)
    for tool_id in tool_ids:
        spec = workflow.tools.get(tool_id)
        runtime = spec.runtime if spec else None
        if runtime and runtime.use_host_python:
            mcp_servers[tool_id] = rewrite_uv_run_python(mcp_servers[tool_id])
        apply_tool_runtime(
            mcp_servers[tool_id],
            runtime,
            run_ctx,
            uv_cache_dir=str(uv_cache),
            context_path=context_path,
        )
    render_dir = mcp_render_dir(
        workspace_root, run_id, bundle.stage_id, bundle.assignment_id
    )
    render_dir.mkdir(parents=True, exist_ok=True)
    archive = turn_archive_dir(
        workspace_root,
        run_id,
        bundle.stage_id,
        bundle.assignment_id,
        attempt,
    )
    return SessionConfig(
        worker=worker,
        cwd=project_root,
        tmp_dir=workspace_root / "tmp",
        mcp_servers=mcp_servers,
        model=model,
        spec_paths=list(bundle.spec_paths),
        rule_ids=list(bundle.rule_ids),
        tool_ids=tool_ids,
        stage_id=bundle.stage_id,
        role=bundle.role,
        attempt=attempt,
        run_id=run_id,
        mcp_render_dir=render_dir,
        archive_dir=archive,
    )
