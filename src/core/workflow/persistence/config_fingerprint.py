"""Resolved workflow configuration fingerprint for resume safety."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.runtime.hashing import sha256_file, stable_hash
from core.runtime.identifiers import resolve_project_path
from core.runtime.tool_runtime import write_json_atomic

from ..config.models import Workflow

SCHEMA_VERSION = 1

IMPLEMENTATION_ROOTS = (
    "src/core",
    "src/utils",
    "harness/tools",
)


def runtime_config_path(workspace_root: Path, run_id: str) -> Path:
    return workspace_root / "memory" / "evidence" / run_id / "runtime-config.json"


def implementation_fingerprint(project_root: Path) -> str:
    """Aggregate hash of Harness implementation sources used by the orchestrator."""
    entries: list[dict[str, str]] = []
    for relative_root in IMPLEMENTATION_ROOTS:
        root = project_root / relative_root
        if not root.exists():
            entries.append({"path": relative_root, "sha256": "missing"})
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix not in {".py", ".yaml", ".yml", ".md", ".toml"}:
                continue
            try:
                rel = str(path.relative_to(project_root)).replace("\\", "/")
            except ValueError:
                continue
            entries.append({"path": rel, "sha256": sha256_file(path)})
    return stable_hash(entries)


def build_runtime_config(
    workflow: Workflow,
    *,
    project_root: Path,
    worker: str = "",
    model: str = "",
) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "workflow_id": workflow.workflow_id,
        "implementation": implementation_fingerprint(project_root),
        "default_rules": list(workflow.default_rules),
        "default_knowledge": list(workflow.default_knowledge),
        "rules": {
            rule_id: _file_ref(project_root, relative)
            for rule_id, relative in sorted(workflow.rules.items())
        },
        "tools": {
            "mcp": {
                tool_id: {
                    "transport": spec.transport,
                    "tool_timeout_sec": spec.tool_timeout_sec,
                    "command": spec.command,
                    "args": list(spec.args),
                    "rules": list(spec.rules),
                    "runtime": None
                    if spec.runtime is None
                    else {
                        "run_context_env": spec.runtime.run_context_env,
                        "context_file": spec.runtime.context_file,
                        "context_file_flag": spec.runtime.context_file_flag,
                        "env_prefix": spec.runtime.env_prefix,
                        "use_host_python": spec.runtime.use_host_python,
                    },
                    "env": {
                        key: stable_hash(value)
                        for key, value in sorted(spec.env.items())
                    },
                }
                for tool_id, spec in sorted(workflow.mcp_tools.items())
            },
            "host_action": {
                action_id: {
                    "command": spec.command,
                    "args": list(spec.args),
                    "timeout_sec": spec.timeout_sec,
                    "env": {
                        key: stable_hash(value)
                        for key, value in sorted(spec.env.items())
                    },
                }
                for action_id, spec in sorted(workflow.host_actions.items())
            },
        },
        "knowledge": {
            kid: {
                "kind": source.kind,
                "path": source.path,
                "provider": source.provider,
            }
            for kid, source in sorted(workflow.knowledge.items())
        },
        "stages": [
            {
                "id": stage.stage_id,
                "spec": _file_ref(project_root, stage.spec),
                "max_attempts": stage.max_attempts,
                "steps": list(stage.steps),
                "context": dict(stage.context),
                "knowledge_decl": stage.knowledge_decl,
                "rules_decl": stage.rules_decl,
                "tools_decl": stage.tools_decl,
            }
            for stage in workflow.stages
        ],
        "assignments": {
            aid: {
                "role": assignment.role,
                "tools_decl": assignment.tools_decl,
                "rules_decl": assignment.rules_decl,
                "knowledge_decl": assignment.knowledge_decl,
            }
            for aid, assignment in sorted(workflow.assignments.items())
        },
        "bundles": {
            aid: bundle.to_dict() for aid, bundle in sorted(workflow.bundles.items())
        },
    }
    fingerprint = stable_hash(payload)
    return {
        "schema_version": SCHEMA_VERSION,
        "workflow_id": workflow.workflow_id,
        "fingerprint": fingerprint,
        "execution": {
            "worker": str(worker),
            "model": str(model),
        },
        "config": payload,
    }


def write_runtime_config(
    workspace_root: Path,
    run_id: str,
    workflow: Workflow,
    *,
    project_root: Path,
    worker: str,
    model: str,
) -> Path:
    path = runtime_config_path(workspace_root, run_id)
    write_json_atomic(
        path,
        build_runtime_config(
            workflow,
            project_root=project_root,
            worker=worker,
            model=model,
        ),
    )
    return path


def assert_runtime_config_matches(
    workspace_root: Path,
    run_id: str,
    workflow: Workflow,
    *,
    project_root: Path,
    worker: str,
    model: str,
) -> None:
    path = runtime_config_path(workspace_root, run_id)
    if not path.is_file():
        raise ValueError("missing runtime configuration; start a new run")
    stored = json.loads(path.read_text(encoding="utf-8"))
    current = build_runtime_config(
        workflow,
        project_root=project_root,
        worker=worker,
        model=model,
    )
    if stored.get("fingerprint") != current["fingerprint"]:
        raise ValueError("workflow configuration changed; start a new run")
    stored_exec = stored.get("execution") or {}
    current_exec = current["execution"]
    if (
        stored_exec.get("worker") != current_exec["worker"]
        or stored_exec.get("model") != current_exec["model"]
    ):
        raise ValueError("runtime execution configuration changed; start a new run")


def _file_ref(project_root: Path, relative: str) -> dict[str, str]:
    path = resolve_project_path(project_root, relative, label="runtime-config file")
    return {
        "path": relative,
        "sha256": sha256_file(path) if path.is_file() else "missing",
    }
