"""Resolved workflow configuration fingerprint for resume safety."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.core.runtime import harness_fs
from backend.core.runtime.hashing import sha256_file, stable_hash
from backend.core.runtime.identifiers import resolve_project_path
from backend.core.runtime.knowledge_providers.local_files import (
    PROVIDER_ID as LOCAL_FILES_PROVIDER,
)
from backend.core.runtime.knowledge_providers.local_files import discover_files_at
from backend.core.runtime.tool_runtime import write_json_atomic
from backend.core.workflow.spec.models import StageSpec
from backend.core.workflow.spec.view import spec_view, spec_view_hash
from backend.settings import records_root

from ..config.models import KnowledgeSource, Workflow

SCHEMA_VERSION = 1

IMPLEMENTATION_ROOTS = (
    "src/backend/core",
    "src/backend/settings.py",
    "harness/tools",
)


def runtime_config_path(workspace_root: Path, run_id: str) -> Path:
    return records_root(workspace_root) / "evidence" / run_id / "runtime-config.json"


def implementation_fingerprint(project_root: Path) -> str:
    """Aggregate hash of Harness implementation sources used by the orchestrator."""
    entries: list[dict[str, str]] = []
    for relative_root in IMPLEMENTATION_ROOTS:
        root = project_root / relative_root
        if not root.exists():
            entries.append({"path": relative_root, "sha256": "missing"})
            continue
        # A root may be a single file (settings.py merged from the former utils/).
        paths = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in paths:
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


def stage_contract_refs(stage_spec: StageSpec, project_root: Path) -> dict[str, Any]:
    """Fingerprint every spec file (content + default/user) and the get_spec view."""
    files: dict[str, dict[str, str]] = {}
    for rel in sorted(stage_spec.sources):
        try:
            found = harness_fs.resolve(project_root, rel)
        except ValueError:
            found = None
        files[rel] = (
            {"source": found.source, "sha256": found.sha256}
            if found is not None
            else {"source": "missing", "sha256": "missing"}
        )
    return {
        "spec": stage_spec.source_path,
        "files": files,
        "spec_view": spec_view_hash(spec_view(stage_spec, project_root)),
    }


def knowledge_source_payload(
    source: KnowledgeSource, project_root: Path
) -> dict[str, Any]:
    """Fingerprint knowledge contents for resume safety (local_files)."""
    payload: dict[str, Any] = {
        "kind": source.kind,
        "path": source.path,
        "provider": source.provider,
    }
    if source.provider == LOCAL_FILES_PROVIDER and source.kind == "local_dir":
        discovered = discover_files_at(project_root, source.path)
        files = [
            {"path": str(entry["path"]), "sha256": str(entry["sha256"])}
            for entry in discovered["files"]
            if entry.get("readable") and "sha256" in entry
        ]
        payload["files"] = files
        payload["fingerprint"] = stable_hash(files)
    return payload


def build_runtime_config(
    workflow: Workflow,
    *,
    project_root: Path,
    worker: str = "",
    model: str = "",
) -> dict[str, Any]:
    stage_specs = _stage_specs_by_id(workflow)
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
            kid: knowledge_source_payload(source, project_root)
            for kid, source in sorted(workflow.knowledge.items())
        },
        "stages": [
            {
                "id": stage.stage_id,
                "contract": stage_contract_refs(
                    stage_specs[stage.stage_id], project_root
                )
                if stage.stage_id in stage_specs
                else {
                    "spec": _file_ref(project_root, stage.spec),
                    "schemas": [],
                },
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


def _stage_specs_by_id(workflow: Workflow) -> dict[str, StageSpec]:
    specs: dict[str, StageSpec] = {}
    for bundle in workflow.bundles.values():
        specs.setdefault(bundle.stage_id, bundle.stage_spec)
    return specs


def _file_ref(project_root: Path, relative: str) -> dict[str, str]:
    path = resolve_project_path(project_root, relative, label="runtime-config file")
    return {
        "path": relative,
        "sha256": sha256_file(path) if path.is_file() else "missing",
    }
