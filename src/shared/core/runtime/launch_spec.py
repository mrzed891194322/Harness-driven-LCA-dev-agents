"""Build SessionLaunchSpec from workflow SessionConfig + TaskBundle."""

from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from core.agents.mcp import tool_entry_to_mcp
from core.agents.permissions import pi_tools
from core.agents.session import SessionConfig
from core.contracts.session_launch_spec import (
    KnowledgeBinding,
    ModelProfile,
    PermissionPolicy,
    SessionLaunchSpec,
    SystemSection,
)
from core.runtime.model_profiles import resolve_model_profile
from core.workflow.config.bundle import TaskBundle
from core.workflow.config.models import Assignment, Stage, Workflow
from core.workflow.execution.handoff import handoff_path
from core.workflow.execution.prompt_build import build_prompt
from core.workflow.execution.session_bind import build_session_config


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _bundle_hash(bundle: TaskBundle) -> str:
    payload = {
        "assignment_id": bundle.assignment_id,
        "rule_ids": bundle.rule_ids,
        "mcp_tool_ids": bundle.mcp_tool_ids,
        "stage_spec": bundle.stage_spec.source_path,
    }
    return _sha(json.dumps(payload, sort_keys=True))


def _input_snapshot_hash(workspace_root: Path, bundle: TaskBundle) -> str:
    parts: list[str] = []
    for item in bundle.stage_spec.inputs:
        path = workspace_root.parent / item.path
        if path.is_file():
            parts.append(_sha(path.read_bytes().hex()))
        else:
            parts.append(f"missing:{item.path}")
    return _sha("|".join(parts))


def compile_permission_policy(
    *,
    role: str,
    mcp_servers: dict[str, dict[str, Any]],
    project_root: Path,
    workspace_root: Path,
) -> PermissionPolicy:
    tools = list(pi_tools(mcp_servers))
    if role == "reviewer":
        write_globs: list[str] = [
            str((workspace_root / "records" / "reviews").resolve()) + "/**",
        ]
        read_globs = [
            str(workspace_root.resolve()) + "/**",
            str(project_root.resolve()) + "/harness/**",
        ]
        tools = [t for t in tools if t in {"read", "grep", "find", "ls", "mcp", "mcpScript"}]
    else:
        write_globs = [str(workspace_root.resolve()) + "/**"]
        read_globs = [
            str(project_root.resolve()) + "/**",
            str(workspace_root.resolve()) + "/**",
        ]
    deny_shell = role == "reviewer"
    if deny_shell:
        tools = [t for t in tools if t != "bash"]
    return PermissionPolicy(
        allowed_tools=tools,
        allowed_read_globs=read_globs,
        allowed_write_globs=write_globs,
        deny_shell=deny_shell,
    )


def build_session_launch_spec(
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
    session_key: str,
    run_context: dict[str, Any],
) -> SessionLaunchSpec:
    config = build_session_config(
        workflow,
        bundle,
        project_root=project_root,
        workspace_root=workspace_root,
        worker=worker,
        model=model,
        stage=stage,
        assignment=assignment,
        run_id=run_id,
        attempt=attempt,
    )
    profile = resolve_model_profile(model, project_root=project_root)
    storage_dir = Path(config.tmp_dir) / "pi-sdk" / session_key
    agent_dir = storage_dir / "agent"
    session_file = storage_dir / "session.jsonl"
    agent_dir.mkdir(parents=True, exist_ok=True)

    prompt_text = build_prompt(
        bundle,
        project_root=project_root,
        rules=workflow.rules,
        run_context=run_context,
    )
    sections = [
        SystemSection(
            id="assignment_prompt",
            content=prompt_text,
            source_hash=_sha(prompt_text),
        )
    ]
    knowledge = [
        KnowledgeBinding(
            id=item.knowledge_id,
            root_path=str((project_root / item.path).resolve()),
            content_hash=_sha(f"{item.knowledge_id}:{item.path}"),
            summary=item.kind,
        )
        for item in bundle.knowledge_sources
    ]
    mcp_bindings: dict[str, dict[str, Any]] = {}
    for name, spec in config.mcp_servers.items():
        entry = tool_entry_to_mcp(name, spec)
        mcp_bindings[name] = {
            "command": entry.get("command"),
            "args": list(entry.get("args") or []),
            "env": dict(entry.get("env") or {}),
            "timeout_ms": int(entry.get("tool_timeout_sec", 60)) * 1000,
            "exposure": "direct",
        }
    handoff = handoff_path(workspace_root, stage.stage_id, assignment.role, attempt)
    handoff_binding = {
        "relative_path": str(handoff.relative_to(project_root))
        if handoff.is_relative_to(project_root)
        else str(handoff),
        "schema_path": bundle.stage_spec.handoff_schema or "",
    }
    return SessionLaunchSpec(
        run_id=run_id,
        stage_id=bundle.stage_id,
        assignment_id=bundle.assignment_id,
        role=bundle.role,
        attempt=attempt,
        session_key=session_key,
        execution_id=uuid.uuid4().hex,
        bundle_hash=_bundle_hash(bundle),
        input_snapshot_hash=_input_snapshot_hash(workspace_root, bundle),
        model_profile=profile,
        system_sections=sections,
        turn_context=dict(run_context),
        knowledge_bindings=knowledge,
        resource_bindings={
            "project_root": str(project_root.resolve()),
            "workspace_root": str(workspace_root.resolve()),
            "host_python": str(Path(sys.executable).resolve()),
            "credentials_dir": str((project_root / ".local" / "credentials").resolve()),
        },
        mcp_bindings=mcp_bindings,
        permission_policy=compile_permission_policy(
            role=bundle.role,
            mcp_servers=config.mcp_servers,
            project_root=project_root,
            workspace_root=workspace_root,
        ),
        session_storage={
            "agent_dir": str(agent_dir.resolve()),
            "session_file": str(session_file.resolve()),
        },
        handoff_binding=handoff_binding,
    )


def launch_spec_from_session_config(
    config: SessionConfig,
    launch: SessionLaunchSpec,
) -> SessionLaunchSpec:
    """Refresh dynamic attempt context without changing static bundle hash."""
    del config
    return launch
