"""Build SessionLaunchSpec from workflow SessionConfig + TaskBundle."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from backend.core.agents import spec_mcp
from backend.core.agents.mcp import tool_entry_to_mcp
from backend.core.agents.permission_rules import resolve_permissions
from backend.core.agents.session import SessionConfig
from backend.core.contracts.session_launch_spec import (
    KnowledgeBinding,
    PermissionPolicy,
    SessionLaunchSpec,
    SystemSection,
)
from backend.core.runtime.model_profiles import resolve_model_profile
from backend.core.workflow.config.bundle import TaskBundle
from backend.core.workflow.config.models import Assignment, Stage, Workflow
from backend.core.workflow.execution.handoff import handoff_path
from backend.core.workflow.execution import generated_prompts
from backend.core.workflow.execution.prompt_build import build_prompt, prompt_segments
from backend.core.workflow.execution.session_bind import build_session_config
from backend.core.workflow.spec.loader import load_stage_spec
from backend.core.workflow.spec.models import StageSpec
from backend.core.workflow.spec.view import spec_view, spec_view_hash
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


def _bundle_hash(bundle: TaskBundle, spec_hash: str = "") -> str:
    payload = {
        "assignment_id": bundle.assignment_id,
        "rule_ids": bundle.rule_ids,
        "mcp_tool_ids": bundle.mcp_tool_ids,
        "stage_spec": bundle.stage_spec.source_path,
        "spec_view": spec_hash,
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
    stage_spec: StageSpec | None = None,
) -> PermissionPolicy:
    """Tools + path scopes come from the stage spec's permissions.yaml (fail closed)."""
    del workspace_root  # scopes are rule-driven, relative to the project root
    resolved = resolve_permissions(
        project_root=project_root,
        role=role,
        rule_refs=rule_refs,
        mcp_servers=mcp_servers,
        stage_spec=stage_spec,
    )
    if resolved.error:
        logger.error("permission rules: %s; session gets no tools (fail closed)", resolved.error)
    return PermissionPolicy(
        allowed_tools=list(resolved.tools),
        allowed_read_globs=list(resolved.read_globs),
        allowed_write_globs=list(resolved.write_globs),
        deny_shell=resolved.deny_shell,
        denied_write_globs=list(resolved.deny_write_globs),
    )


def compile_stage_spec(
    bundle: TaskBundle, project_root: Path
) -> tuple[StageSpec | None, str | None]:
    """Re-read the stage spec at session creation (user override first).

    No caching: a GUI edit applies from the next session. Errors fail closed.
    """
    relative = bundle.stage_spec.source_path
    try:
        spec = load_stage_spec(
            project_root / relative, project_root=project_root, relative=relative
        )
    except (OSError, ValueError) as exc:
        return None, f"{relative}: {exc}"
    return spec, None


def spec_context_section(view: dict[str, Any] | None, error: str | None) -> str:
    if view is None:
        return (
            "# 本阶段交付规格（宿主注入）\n"
            f"spec 缺失或无效，本会话没有任何工具（fail closed）：{error}\n"
            "请用 status=blocked 说明原因；无法交卷时宿主会按协议处理。"
        )
    return (
        "# 本阶段交付规格（宿主注入，等同 spec_mcp.get_spec() 的结果）\n"
        "以 spec_mcp 为准：schema、示例、验收要点都在下面；如有更新，调用 get_spec 取最新版本。\n"
        "```json\n" + json.dumps(view, ensure_ascii=False, indent=2) + "\n```"
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

    stage_spec, spec_error = compile_stage_spec(bundle, project_root)
    view = spec_view(stage_spec, project_root) if stage_spec is not None else None
    view_hash = spec_view_hash(view) if view is not None else ""
    handoff = handoff_path(workspace_root, stage.stage_id, assignment.role, attempt)
    session_servers: dict[str, dict[str, Any]] = dict(config.mcp_servers)
    if stage_spec is not None:
        try:
            session_servers[spec_mcp.SERVER_NAME] = spec_mcp.spec_mcp_server(
                project_root=project_root,
                workspace_root=workspace_root,
                run_id=run_id,
                stage_id=bundle.stage_id,
                role=bundle.role,
                attempt=attempt,
                assignment_id=bundle.assignment_id,
                spec_relative=stage_spec.source_path,
                handoff_relative=str(handoff.relative_to(workspace_root))
                if handoff.is_relative_to(workspace_root)
                else str(handoff),
                metadata=dict(bundle.context),
                uv_cache_dir=str(project_root / ".uv-cache"),
            )
        except (OSError, ValueError) as exc:
            stage_spec, spec_error, view = None, f"spec_mcp: {exc}", None
    prompt_text = build_prompt(
        bundle,
        project_root=project_root,
        rules=workflow.rules,
        run_context=run_context,
    )
    spec_text = spec_context_section(view, spec_error)
    policy = compile_permission_policy(
        role=bundle.role,
        mcp_servers=session_servers if stage_spec is not None else {},
        project_root=project_root,
        workspace_root=workspace_root,
        rule_refs=assignment.permissions_decl,
        stage_spec=stage_spec,
    )
    # Rendered fresh for every session (fixed order); a missing variable raises.
    generated = generated_prompts.render_session(project_root, policy)
    for seg in generated:
        seg["section"] = "generated_prompts"
    generated_text = "\n\n".join(seg["content"] for seg in generated)
    sections = [
        SystemSection(id="spec_context", content=spec_text, source_hash=_sha(spec_text)),
        SystemSection(
            id="assignment_prompt",
            content=prompt_text,
            source_hash=_sha(prompt_text),
        ),
    ]
    if generated_text:
        sections.append(
            SystemSection(
                id="generated_prompts",
                content=generated_text,
                source_hash=_sha(generated_text),
            )
        )
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
    for name, spec in session_servers.items():
        entry = tool_entry_to_mcp(name, spec)
        mcp_bindings[name] = {
            "command": entry.get("command"),
            "args": list(entry.get("args") or []),
            "env": {**openlca_env(project_root), **dict(entry.get("env") or {})},
            "timeout_ms": int(entry.get("tool_timeout_sec", 60)) * 1000,
            "exposure": "direct",
        }
    handoff_binding = {
        "relative_path": str(handoff.relative_to(project_root))
        if handoff.is_relative_to(project_root)
        else str(handoff),
        "schema_path": bundle.stage_spec.handoff_schema or "",
    }
    segments = prompt_segments(
        bundle, project_root=project_root, rules=workflow.rules, run_context=run_context
    )
    launch = SessionLaunchSpec(
        run_id=run_id,
        stage_id=bundle.stage_id,
        assignment_id=bundle.assignment_id,
        role=bundle.role,
        attempt=attempt,
        session_key=session_key,
        execution_id=uuid.uuid4().hex,
        bundle_hash=_bundle_hash(bundle, view_hash),
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
        permission_policy=policy,
        session_storage={
            "agent_dir": str(agent_dir.resolve()),
            "session_file": str(session_file.resolve()),
        },
        handoff_binding=handoff_binding,
    )
    for seg in segments:
        seg["section"] = "assignment_prompt"
    launch.prompt_segments = [*segments, *generated]
    launch.spec_view = view
    launch.spec_view_hash = view_hash
    launch.spec_sources = dict(stage_spec.sources) if stage_spec is not None else {}
    return launch


def launch_spec_from_session_config(
    config: SessionConfig,
    launch: SessionLaunchSpec,
) -> SessionLaunchSpec:
    """Refresh dynamic attempt context without changing static bundle hash."""
    del config
    return launch
