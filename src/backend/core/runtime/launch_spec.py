"""Build SessionLaunchSpec from workflow SessionConfig + TaskBundle."""

from __future__ import annotations

import logging

import hashlib
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from backend.core.agents.mcp import tool_entry_to_mcp
from backend.core.agents.permission_rules import resolve_permissions
from backend.core.agents.session import SessionConfig
from backend.core.contracts.session_launch_spec import (
    KnowledgeBinding,
    ModelProfile,
    PermissionPolicy,
    SessionLaunchSpec,
    SystemSection,
)
from backend.core.runtime.model_profiles import resolve_model_profile
from backend.core.workflow.config.bundle import TaskBundle
from backend.core.workflow.config.models import Assignment, Stage, Workflow
from backend.core.workflow.execution.handoff import handoff_path
from backend.core.workflow.execution.prompt_build import build_prompt
from backend.core.workflow.execution.session_bind import build_session_config
from backend.settings import parse_env_file


logger = logging.getLogger(__name__)

def openlca_env(project_root: Path) -> dict[str, str]:
    """openLCA IPC settings for MCP servers, read at session creation.

    MCP servers are children of the long-lived pi-runtime, whose environment is
    fixed at `npm run dev`. Passing the current values per session keeps a port
    changed in the settings page effective for the next run without a restart.
    """
    values = parse_env_file(project_root / ".env")
    env: dict[str, str] = {}
    for key in ("OPENLCA_IPC_HOST", "OPENLCA_IPC_PORT"):
        value = (values.get(key) or os.environ.get(key) or "").strip()
        if value:
            env[key] = value
    return env


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
    workspace_root: Path | None = None,
    rule_refs: list[str] | None = None,
) -> PermissionPolicy:
    """Tools + path scopes come from harness/rules/permissions (fail closed)."""
    del workspace_root  # scopes are rule-driven, relative to the project root
    resolved = resolve_permissions(
        project_root=project_root,
        role=role,
        rule_refs=rule_refs,
        mcp_servers=mcp_servers,
    )
    if resolved.error:
        logger.error("permission rules: %s; session gets no tools (fail closed)", resolved.error)
    return PermissionPolicy(
        allowed_tools=list(resolved.tools),
        allowed_read_globs=list(resolved.read_globs),
        allowed_write_globs=list(resolved.write_globs),
        deny_shell=resolved.deny_shell,
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
            "env": {**openlca_env(project_root), **dict(entry.get("env") or {})},
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
            rule_refs=assignment.permissions_decl,
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
