"""Load workflow YAML (stdlib assembly map; no Python providers, no reuse)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.agents.mcp import DEFAULT_TOOL_TIMEOUT_SEC, validate_stdio_server
from core.runtime.capabilities import HarnessCapabilities, base_capabilities
from core.runtime.identifiers import (
    require_identifier,
    require_relative_path,
    resolve_project_path,
)
from core.runtime.tool_runtime import ToolRuntimeSpec
from core.workflow.spec.loader import load_stage_spec

from .lists import parse_optional_list_field, reject_user_seq_declaration, resolve_list
from .models import Assignment, KnowledgeSource, Stage, ToolSpec, Workflow
from .resolve import attach_bundles
from .yaml_strict import load_yaml_strict

TOP_LEVEL_KEYS = frozenset(
    {"id", "max_attempts", "registry", "defaults", "stages", "assignments"}
)
REGISTRY_KEYS = frozenset({"rules", "tools", "knowledge"})
FORBIDDEN_REGISTRY = frozenset({"checkers", "hooks", "handoff_validators"})
DEFAULTS_KEYS = frozenset({"rules", "knowledge"})
TOOL_KEYS = frozenset(
    {
        "transport",
        "command",
        "args",
        "url",
        "env",
        "headers",
        "rules",
        "runtime",
        "tool_timeout_sec",
    }
)
TOOL_RUNTIME_KEYS = frozenset(
    {
        "run_context_env",
        "context_file",
        "context_file_flag",
        "env_prefix",
        "use_host_python",
    }
)
KNOWLEDGE_KEYS = frozenset({"kind", "path", "provider"})
STAGE_KEYS = frozenset(
    {"id", "spec", "max_attempts", "steps", "knowledge", "rules", "tools", "context"}
)
ASSIGNMENT_KEYS = frozenset({"role", "tools", "rules", "knowledge"})


def reject_unknown_keys(
    obj: dict[str, Any], allowed: frozenset[str], label: str
) -> None:
    unknown = set(obj) - allowed
    if unknown:
        raise ValueError(f"{label}: unknown key(s) {sorted(unknown)}")


def _require_positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer, got {value!r}")
    return value


def load_workflow(
    path: Path,
    *,
    project_root: Path,
    capabilities: HarnessCapabilities | None = None,
    document: dict[str, Any] | None = None,
) -> Workflow:
    caps = capabilities if capabilities is not None else base_capabilities()
    raw = (
        document
        if document is not None
        else read_workflow_document(path, project_root=project_root)
    )
    workflow = _parse_workflow(raw, source_path=path)
    attach_bundles(workflow, project_root, caps)
    _validate_files(workflow, project_root)
    return workflow


def read_workflow_document(path: Path, *, project_root: Path) -> dict[str, Any]:
    del project_root
    raw = _read_yaml(path)
    if raw.get("reuse") or raw.get("stage_overrides"):
        raise ValueError(
            f"{path}: reuse/stage_overrides are not supported; "
            "each workflow YAML must be a complete assembly map"
        )
    if "runtime_spec" in raw or "task_spec" in str(raw.get("assignments") or {}):
        # task_spec checked per-assignment below; reject top-level runtime_spec here.
        pass
    if "runtime_spec" in raw:
        raise ValueError(
            f"{path}: runtime_spec was removed; core embeds the generic runtime protocol"
        )
    _reject_user_seq_fields(raw, path)
    reject_unknown_keys(raw, TOP_LEVEL_KEYS, str(path))
    return raw


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = load_yaml_strict(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: workflow YAML must be a mapping")
    return payload


def _reject_user_seq_fields(raw: dict[str, Any], path: Path) -> None:
    defaults = raw.get("defaults") or {}
    if isinstance(defaults, dict):
        for key in ("rules", "knowledge", "tools"):
            if key in defaults:
                reject_user_seq_declaration(
                    defaults.get(key), label=f"{path}: defaults.{key}"
                )
    for stage in raw.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        stage_id = stage.get("id") or "?"
        for key in ("rules", "knowledge", "tools"):
            if key in stage:
                reject_user_seq_declaration(
                    stage.get(key), label=f"{path}: stage {stage_id} {key}"
                )
    for assignment_id, assignment in (raw.get("assignments") or {}).items():
        if not isinstance(assignment, dict):
            continue
        for key in ("rules", "knowledge", "tools"):
            if key in assignment:
                reject_user_seq_declaration(
                    assignment.get(key),
                    label=f"{path}: assignment {assignment_id} {key}",
                )


def _parse_workflow(raw: dict[str, Any], *, source_path: Path) -> Workflow:
    reject_unknown_keys(raw, TOP_LEVEL_KEYS, str(source_path))
    for banned in ("capabilities", "reuse", "stage_overrides", "hooks", "runtime_spec"):
        if banned in raw:
            raise ValueError(f"{source_path}: '{banned}' is not supported")
    workflow_id = require_identifier(str(raw.get("id") or ""), label="workflow id")
    registry = raw.get("registry") or {}
    if not isinstance(registry, dict):
        raise ValueError(f"{source_path}: registry must be a mapping")
    forbidden = set(registry) & FORBIDDEN_REGISTRY
    if forbidden:
        raise ValueError(
            f"{source_path}: registry.{sorted(forbidden)[0]} Python providers "
            "are forbidden; declare deterministic checks in stage spec.yaml "
            "as stdio MCP calls"
        )
    if any(
        "provider" in str(registry.get(section) or {}) for section in FORBIDDEN_REGISTRY
    ):
        raise ValueError(f"{source_path}: provider imports are forbidden")
    # Also reject provider: under tools? tools don't use provider for callables.
    reject_unknown_keys(registry, REGISTRY_KEYS, f"{source_path}: registry")

    rules: dict[str, str] = {}
    for rule_id, rule_path in dict(registry.get("rules") or {}).items():
        rid = require_identifier(str(rule_id), label="rule id")
        rules[rid] = require_relative_path(str(rule_path), label=f"rule {rid} path")

    knowledge: dict[str, KnowledgeSource] = {}
    for knowledge_id, spec in dict(registry.get("knowledge") or {}).items():
        if not isinstance(spec, dict):
            raise ValueError(
                f"{source_path}: knowledge {knowledge_id} must be a mapping"
            )
        reject_unknown_keys(
            spec, KNOWLEDGE_KEYS, f"{source_path}: knowledge {knowledge_id}"
        )
        kid = require_identifier(str(knowledge_id), label="knowledge id")
        knowledge[kid] = KnowledgeSource(
            knowledge_id=kid,
            kind=str(spec.get("kind") or "local_dir"),
            path=require_relative_path(
                str(spec.get("path") or ""), label=f"knowledge {kid} path"
            ),
            provider=require_identifier(
                str(spec.get("provider") or "local_files"), label="provider id"
            ),
        )

    tools: dict[str, ToolSpec] = {}
    for tool_id, spec in dict(registry.get("tools") or {}).items():
        if not isinstance(spec, dict):
            raise ValueError(f"{source_path}: tool {tool_id} must be a mapping")
        if "provider" in spec:
            raise ValueError(
                f"{source_path}: tool {tool_id}: provider imports are forbidden"
            )
        reject_unknown_keys(spec, TOOL_KEYS, f"{source_path}: tool {tool_id}")
        tid = require_identifier(str(tool_id), label="tool id")
        validate_stdio_server(tid, spec)
        tools[tid] = ToolSpec(
            tool_id=tid,
            transport=str(spec.get("transport") or "stdio"),
            command=spec.get("command"),
            args=[str(item) for item in spec.get("args") or []],
            url=spec.get("url"),
            env={str(k): str(v) for k, v in dict(spec.get("env") or {}).items()},
            headers={
                str(k): str(v) for k, v in dict(spec.get("headers") or {}).items()
            },
            rules=[
                require_identifier(str(item), label="rule id")
                for item in spec.get("rules") or []
            ],
            runtime=_parse_tool_runtime(spec, label=f"{source_path}: tool {tid}"),
            tool_timeout_sec=spec.get("tool_timeout_sec", DEFAULT_TOOL_TIMEOUT_SEC),
        )

    defaults = raw.get("defaults") or {}
    reject_unknown_keys(defaults, DEFAULTS_KEYS, f"{source_path}: defaults")

    assignments: dict[str, Assignment] = {}
    for assignment_id, spec in dict(raw.get("assignments") or {}).items():
        if not isinstance(spec, dict):
            raise ValueError(
                f"{source_path}: assignment {assignment_id} must be a mapping"
            )
        if "task_spec" in spec:
            raise ValueError(
                f"{source_path}: assignment {assignment_id}: task_spec was removed; "
                "bind role instructions via rules.add"
            )
        reject_unknown_keys(
            spec, ASSIGNMENT_KEYS, f"{source_path}: assignment {assignment_id}"
        )
        aid = require_identifier(str(assignment_id), label="assignment id")
        role = str(spec.get("role") or "")
        if role not in {"executor", "reviser", "reviewer"}:
            raise ValueError(
                f"{source_path}: assignment {aid} has invalid role {role!r}"
            )
        assignments[aid] = Assignment(
            assignment_id=aid,
            role=role,
            tools_decl=parse_optional_list_field(spec["tools"])
            if "tools" in spec
            else None,
            rules_decl=parse_optional_list_field(spec["rules"])
            if "rules" in spec
            else None,
            knowledge_decl=parse_optional_list_field(spec["knowledge"])
            if "knowledge" in spec
            else None,
        )

    if "max_attempts" in raw:
        default_attempts = _require_positive_int(
            raw.get("max_attempts"), label=f"{source_path}: max_attempts"
        )
    else:
        default_attempts = 3

    stages: list[Stage] = []
    for spec in raw.get("stages") or []:
        if not isinstance(spec, dict):
            raise ValueError(f"{source_path}: each stage must be a mapping")
        for banned in ("checks", "hooks", "outputs", "spec_additions"):
            if banned in spec:
                raise ValueError(
                    f"{source_path}: stage {spec.get('id')}: '{banned}' moved to "
                    "stage spec.yaml (machine contract)"
                )
        reject_unknown_keys(spec, STAGE_KEYS, f"{source_path}: stage")
        stage_id = require_identifier(str(spec.get("id") or ""), label="stage id")
        steps: list[str] = []
        for step in spec.get("steps") or []:
            if isinstance(step, dict) and step.get("assignment"):
                steps.append(
                    require_identifier(str(step["assignment"]), label="assignment id")
                )
            else:
                steps.append(require_identifier(str(step), label="assignment id"))
        stage_attempts = (
            _require_positive_int(
                spec.get("max_attempts"),
                label=f"{source_path}: stage {stage_id} max_attempts",
            )
            if "max_attempts" in spec
            else default_attempts
        )
        stages.append(
            Stage(
                stage_id=stage_id,
                spec=require_relative_path(
                    str(spec.get("spec") or ""), label=f"{stage_id} spec"
                ),
                max_attempts=stage_attempts,
                steps=steps,
                knowledge_decl=parse_optional_list_field(spec["knowledge"])
                if "knowledge" in spec
                else None,
                rules_decl=parse_optional_list_field(spec["rules"])
                if "rules" in spec
                else None,
                tools_decl=parse_optional_list_field(spec["tools"])
                if "tools" in spec
                else None,
                context=_parse_context(
                    spec.get("context"),
                    label=f"{source_path}: stage {stage_id} context",
                ),
            )
        )

    return Workflow(
        workflow_id=workflow_id,
        max_attempts=default_attempts,
        rules=rules,
        tools=tools,
        knowledge=knowledge,
        default_rules=[
            require_identifier(str(item), label="rule id")
            for item in resolve_list([], defaults.get("rules"))
        ],
        default_knowledge=[
            require_identifier(str(item), label="knowledge id")
            for item in resolve_list([], defaults.get("knowledge"))
        ],
        stages=stages,
        assignments=assignments,
        source_path=source_path,
    )


def _parse_tool_runtime(spec: dict[str, Any], *, label: str) -> ToolRuntimeSpec | None:
    raw = spec.get("runtime")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"{label}: runtime must be a mapping")
    reject_unknown_keys(raw, TOOL_RUNTIME_KEYS, f"{label}: runtime")
    return ToolRuntimeSpec(
        run_context_env=bool(raw.get("run_context_env", False)),
        context_file=bool(raw.get("context_file", False)),
        context_file_flag=str(raw.get("context_file_flag") or "--context-file"),
        env_prefix=str(raw["env_prefix"]) if raw.get("env_prefix") else None,
        use_host_python=bool(raw.get("use_host_python", False)),
    )


def _parse_context(value: Any, *, label: str) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return dict(value)


def _validate_files(workflow: Workflow, project_root: Path) -> None:
    for rule_id, relative in workflow.rules.items():
        path = resolve_project_path(project_root, relative, label=f"rule {rule_id}")
        if not path.is_file():
            raise ValueError(f"missing rule file for {rule_id}: {relative}")
    for kid, source in workflow.knowledge.items():
        path = resolve_project_path(project_root, source.path, label=f"knowledge {kid}")
        if not path.exists():
            raise ValueError(f"missing knowledge path for {kid}: {source.path}")
    for stage in workflow.stages:
        path = resolve_project_path(
            project_root, stage.spec, label=f"{stage.stage_id} spec"
        )
        if not path.is_file():
            raise ValueError(f"missing stage spec: {stage.spec}")
        # Eager-parse to fail fast; bundles already hold parsed StageSpec.
        load_stage_spec(path, project_root=project_root, relative=stage.spec)
    for tool in workflow.tools.values():
        for arg in tool.args:
            if arg.endswith(".py"):
                candidate = project_root / arg
                if candidate.is_file() or Path(arg).is_file():
                    continue
