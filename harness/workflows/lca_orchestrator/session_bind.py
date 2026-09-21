"""Bind YAML assignment materials into a backend-agnostic SessionConfig."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness.tools.control_openlca.utils.workflow import _write_json_atomic
from scripts.agent_sdk.archive import mcp_render_dir, turn_archive_dir
from scripts.agent_sdk.mcp import mcp_servers_for_tools
from scripts.agent_sdk.models import load_worker_model
from scripts.agent_sdk.session import SessionConfig
from scripts.agent_sdk.uv_env import ensure_uv_cache_dir

from .bundle import TaskBundle
from .models import Assignment, Stage, Workflow

LCA_ENV_TOOLS = ("control_openlca", "lca_artifacts")
CONTEXT_FILE_FLAG = "--context-file"


def mcp_context_path(
    workspace_root: Path, run_id: str, stage_id: str, role: str
) -> Path:
    return workspace_root / "tmp" / "mcp-context" / run_id / stage_id / f"{role}.json"


def write_mcp_context(
    workspace_root: Path,
    *,
    run_id: str,
    stage_id: str,
    role: str,
    attempt: int,
) -> Path:
    path = mcp_context_path(workspace_root, run_id, stage_id, role)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_atomic(
        path,
        {
            "run_id": run_id,
            "stage": stage_id,
            "attempt": attempt,
            "role": role,
            "workspace": str(workspace_root),
        },
    )
    return path.resolve()


def _with_context_file(args: list[str], path: Path) -> list[str]:
    rendered = list(args)
    flag = CONTEXT_FILE_FLAG
    if flag in rendered:
        index = rendered.index(flag)
        if index + 1 < len(rendered) and not str(rendered[index + 1]).startswith("-"):
            rendered[index + 1] = str(path)
            return rendered
        rendered.insert(index + 1, str(path))
        return rendered
    return rendered + [flag, str(path)]


def build_session_config(
    workflow: Workflow,
    bundle: TaskBundle,
    *,
    project_root: Path,
    workspace_root: Path,
    worker: str,
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
    extra_env = {
        "LCA_RUN_ID": run_id,
        "LCA_STAGE": bundle.stage_id,
        "LCA_ATTEMPT": str(attempt),
        "LCA_ROLE": bundle.role,
        "LCA_WORKSPACE": str(workspace_root),
        "UV_CACHE_DIR": str(uv_cache),
    }
    context_path = None
    if any(tool_id in LCA_ENV_TOOLS for tool_id in tool_ids):
        context_path = write_mcp_context(
            workspace_root,
            run_id=run_id,
            stage_id=bundle.stage_id,
            role=bundle.role,
            attempt=attempt,
        )
    for tool_id in tool_ids:
        server = mcp_servers[tool_id]
        merged: dict[str, Any] = {
            **server.get("env", {}),
            "UV_CACHE_DIR": str(uv_cache),
        }
        if tool_id in LCA_ENV_TOOLS:
            merged.update(extra_env)
            if context_path is not None:
                server["args"] = _with_context_file(
                    list(server.get("args") or []), context_path
                )
        server["env"] = merged
    render_dir = mcp_render_dir(workspace_root, run_id, bundle.stage_id, bundle.role)
    render_dir.mkdir(parents=True, exist_ok=True)
    archive = turn_archive_dir(
        workspace_root,
        run_id,
        bundle.stage_id,
        bundle.role,
        attempt,
    )
    return SessionConfig(
        worker=worker,
        cwd=project_root,
        tmp_dir=workspace_root / "tmp",
        mcp_servers=mcp_servers,
        model=load_worker_model(worker, project_root),
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
