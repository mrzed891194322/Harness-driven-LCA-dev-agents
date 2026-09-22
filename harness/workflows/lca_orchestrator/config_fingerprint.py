"""Resolved workflow configuration fingerprint for resume safety."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness.runtime.hashing import sha256_file, stable_hash
from harness.runtime.identifiers import resolve_project_path
from harness.runtime.tool_runtime import write_json_atomic

from .models import Workflow

SCHEMA_VERSION = 1


def runtime_config_path(workspace_root: Path, run_id: str) -> Path:
    return workspace_root / "memory" / "evidence" / run_id / "runtime-config.json"


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
        "capability_ids": list(workflow.capability_ids),
        "runtime_spec": _file_ref(project_root, workflow.runtime_spec),
        "default_rules": list(workflow.default_rules),
        "default_knowledge": list(workflow.default_knowledge),
        "reviewer_passed_hooks": list(workflow.reviewer_passed_hooks),
        "rules": {
            rule_id: _file_ref(project_root, relative)
            for rule_id, relative in sorted(workflow.rules.items())
        },
        "tools": {
            tool_id: {
                "transport": spec.transport,
                "command": spec.command,
                "args": list(spec.args),
                "url": spec.url,
                "rules": list(spec.rules),
                "runtime": None
                if spec.runtime is None
                else {
                    "run_context_env": spec.runtime.run_context_env,
                    "context_file": spec.runtime.context_file,
                    "context_file_flag": spec.runtime.context_file_flag,
                    "env_prefix": spec.runtime.env_prefix,
                },
                "env": {
                    key: stable_hash(value) for key, value in sorted(spec.env.items())
                },
                "headers": {
                    key: stable_hash(value)
                    for key, value in sorted(spec.headers.items())
                },
            }
            for tool_id, spec in sorted(workflow.tools.items())
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
                "spec_additions": [
                    _file_ref(project_root, item) for item in stage.spec_additions
                ],
                "outputs": list(stage.outputs),
                "checks": [check.to_dict() for check in stage.checks],
                "context": dict(stage.context),
                "knowledge_decl": stage.knowledge_decl,
                "rules_decl": stage.rules_decl,
                "tools_decl": stage.tools_decl,
                "hooks_decl": stage.reviewer_passed_hooks_decl,
            }
            for stage in workflow.stages
        ],
        "assignments": {
            aid: {
                "role": assignment.role,
                "task_spec": _file_ref(project_root, assignment.task_spec)
                if assignment.task_spec
                else "",
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
        raise ValueError(
            "v2/legacy checkpoint cannot be resumed by v3; start a new run"
        )
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
