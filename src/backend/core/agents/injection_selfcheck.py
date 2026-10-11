"""Empty-session self-check: create a real Pi session (no model call), diff, release.

Used by ``npm run doctor`` and tests. Uses an unreachable local model profile so
nothing is ever sent, and the real spec_mcp server for stage 01 so the critical
items (model, spec_mcp tools, path-guard hook) are all exercised. Runs in strict
semantics regardless of ``HARNESS_INJECTION_STRICT``.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from backend.core.agents import injection, spec_mcp
from backend.core.agents.mcp import tool_entry_to_mcp
from backend.core.contracts.session_launch_spec import (
    ModelProfile,
    PermissionPolicy,
    SessionLaunchSpec,
    SystemSection,
)

SELFCHECK_TEXT = "# injection self-check\n这是注入自检会话，不会调用模型。"


def selfcheck_launch_spec(project_root: Path, *, run_id: str = "doctor-selfcheck") -> SessionLaunchSpec:
    key = f"selfcheck-{uuid.uuid4().hex[:8]}"
    workspace = project_root / "workspace"
    entry = spec_mcp.spec_mcp_server(
        project_root=project_root,
        workspace_root=workspace,
        run_id=run_id,
        stage_id="01-intake-gate",
        role="reviewer",
        attempt=1,
        assignment_id=key,
        spec_relative="harness/specs/01-intake-gate/spec.yaml",
        handoff_relative=f"tmp/{run_id}/handoff.json",
    )
    mcp = tool_entry_to_mcp(spec_mcp.SERVER_NAME, entry)
    storage = project_root / ".local" / "runs" / run_id / "pi" / key
    return SessionLaunchSpec(
        run_id=run_id,
        stage_id="selfcheck",
        assignment_id=key,
        role="reviewer",
        attempt=1,
        session_key=key,
        execution_id=key,
        bundle_hash="selfcheck",
        input_snapshot_hash="selfcheck",
        model_profile=ModelProfile(
            profile_id="selfcheck",
            provider="selfcheck-local",
            model_id="selfcheck-model",
            api_type="openai-completions",
            base_url="http://127.0.0.1:9/v1",
        ),
        system_sections=[SystemSection(id="selfcheck", content=SELFCHECK_TEXT,
                                       source_hash=injection.sha256(SELFCHECK_TEXT))],
        turn_context={},
        knowledge_bindings=[],
        resource_bindings={"project_root": str(project_root.resolve())},
        mcp_bindings={
            spec_mcp.SERVER_NAME: {
                "command": mcp.get("command"),
                "args": list(mcp.get("args") or []),
                "env": dict(mcp.get("env") or {}),
                "timeout_ms": 60_000,
                "exposure": "direct",
            }
        },
        permission_policy=PermissionPolicy(
            allowed_tools=["read", f"mcp__{spec_mcp.SERVER_NAME}__*"],
            allowed_read_globs=["harness/**"],
            allowed_write_globs=[],
        ),
        session_storage={
            "agent_dir": str(storage / "agent"),
            "session_file": str(storage / "session.jsonl"),
        },
    )


def run_selfcheck(runtime: Any, project_root: Path) -> dict[str, Any]:
    """``runtime`` is a PiRuntimeClient. Returns the diff (plus ``ok``)."""
    launch = selfcheck_launch_spec(project_root)
    try:
        result = runtime.request("session.create", {"launch_spec": launch.to_dict()}, timeout=120.0)
        check = injection.write_session_snapshots(project_root, launch, result.get("effective"))
    finally:
        try:
            runtime.request("session.release", {"session_key": launch.session_key}, timeout=30.0)
        except Exception:
            pass
    check["ok"] = not check["critical_mismatch"] and bool(
        (result.get("effective") or {}).get("captured")
    )
    check["snapshot_dir"] = str(
        injection.session_snapshot_dir(project_root, launch.run_id, launch.stage_id, launch.role, 1)
    )
    return check
