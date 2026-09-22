"""Load and merge workflow YAML."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from harness.runtime.capabilities import HarnessCapabilities
from harness.runtime.identifiers import (
    require_identifier,
    require_relative_path,
    require_workspace_output,
    resolve_project_path,
)
from harness.runtime.tool_runtime import ToolRuntimeSpec

from .bundle import CheckRef
from .lists import (
    merge_list_declarations,
    parse_optional_list_field,
    reject_user_seq_declaration,
    resolve_list,
)
from .models import Assignment, KnowledgeSource, Stage, ToolSpec, Workflow
from .resolve import attach_bundles
from .yaml_strict import load_yaml_strict

FORBIDDEN_PROMPT_KEYS = frozenset({"prompt", "extra_prompt"})

TOP_LEVEL_KEYS = frozenset(
    {
        "id",
        "reuse",
        "runtime_spec",
        "max_attempts",
        "registry",
        "defaults",
        "hooks",
        "stages",
        "assignments",
        "stage_overrides",
        "capabilities",
    }
)
REGISTRY_KEYS = frozenset({"rules", "tools", "knowledge"})
DEFAULTS_KEYS = frozenset({"rules", "knowledge"})
HOOKS_KEYS = frozenset({"on_reviewer_passed"})
TOOL_KEYS = frozenset(
    {"transport", "command", "args", "url", "env", "headers", "rules", "runtime"}
)
TOOL_RUNTIME_KEYS = frozenset(
    {"run_context_env", "context_file", "context_file_flag", "env_prefix"}
)
KNOWLEDGE_KEYS = frozenset({"kind", "path", "provider"})
STAGE_KEYS = frozenset(
    {
        "id",
        "spec",
        "max_attempts",
        "steps",
        "spec_additions",
        "outputs",
        "checks",
        "knowledge",
        "rules",
        "tools",
        "hooks",
        "context",
    }
)
STAGE_OVERRIDE_KEYS = frozenset(
    {
        "spec",
        "max_attempts",
        "spec_additions",
        "steps",
        "outputs",
        "checks",
        "knowledge",
        "rules",
        "tools",
        "hooks",
        "context",
    }
)
ASSIGNMENT_KEYS = frozenset({"role", "task_spec", "tools", "rules", "knowledge"})
CHECK_KEYS = frozenset({"id"})


def reject_unknown_keys(
    obj: dict[str, Any], allowed: frozenset[str], label: str
) -> None:
    unknown = set(obj) - allowed
    if unknown:
        raise ValueError(f"{label}: unknown key(s) {sorted(unknown)}")


def _require_bool(value: Any, *, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean, got {value!r}")
    return value


def _require_positive_int(value: Any, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer, got {value!r}")
    return value


def _require_str_list(value: Any, *, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{label} items must be strings, got {item!r}")
        result.append(item)
    return result


def load_workflow(
    path: Path,
    *,
    project_root: Path,
    capabilities: HarnessCapabilities | None = None,
) -> Workflow:
    raw = _read_yaml(path)
    _reject_prompt_fields(raw, path)
    _reject_user_seq_fields(raw, path)
    reject_unknown_keys(raw, TOP_LEVEL_KEYS | frozenset({"reuse"}), str(path))
    if raw.get("reuse"):
        base_path = resolve_project_path(
            project_root, str(raw["reuse"]), label=f"{path}: reuse"
        )
        base_raw = _read_yaml(base_path)
        _reject_prompt_fields(base_raw, base_path)
        _reject_user_seq_fields(base_raw, base_path)
        reject_unknown_keys(base_raw, TOP_LEVEL_KEYS, str(base_path))
        if base_raw.get("reuse"):
            raise ValueError(f"{path}: nested reuse is not supported")
        raw = _merge_workflow(base_raw, raw, overlay_path=path)
    workflow = _parse_workflow(raw, source_path=path)
    _validate_files(workflow, project_root)
    attach_bundles(workflow, project_root, capabilities)
    return workflow


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = load_yaml_strict(path)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: workflow YAML must be a mapping")
    return payload


def _reject_prompt_fields(raw: dict[str, Any], path: Path) -> None:
    stack: list[Any] = [raw]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if key in FORBIDDEN_PROMPT_KEYS:
                    raise ValueError(
                        f"{path}: YAML must not contain task text field {key!r}"
                    )
                stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)


def _reject_user_seq_fields(raw: dict[str, Any], path: Path) -> None:
    """User YAML may not author ``seq``; merge may introduce it afterward."""
    defaults = raw.get("defaults") or {}
    if isinstance(defaults, dict):
        for key in ("rules", "knowledge", "tools"):
            if key in defaults:
                reject_user_seq_declaration(
                    defaults.get(key), label=f"{path}: defaults.{key}"
                )
    hooks = raw.get("hooks") or {}
    if isinstance(hooks, dict) and "on_reviewer_passed" in hooks:
        reject_user_seq_declaration(
            hooks.get("on_reviewer_passed"),
            label=f"{path}: hooks.on_reviewer_passed",
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
        stage_hooks = stage.get("hooks") or {}
        if isinstance(stage_hooks, dict) and "on_reviewer_passed" in stage_hooks:
            reject_user_seq_declaration(
                stage_hooks.get("on_reviewer_passed"),
                label=f"{path}: stage {stage_id} hooks.on_reviewer_passed",
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
    for stage_id, patch in (raw.get("stage_overrides") or {}).items():
        if not isinstance(patch, dict):
            continue
        for key in ("rules", "knowledge", "tools"):
            if key in patch:
                reject_user_seq_declaration(
                    patch.get(key),
                    label=f"{path}: stage_overrides.{stage_id} {key}",
                )
        stage_hooks = patch.get("hooks") or {}
        if isinstance(stage_hooks, dict) and "on_reviewer_passed" in stage_hooks:
            reject_user_seq_declaration(
                stage_hooks.get("on_reviewer_passed"),
                label=f"{path}: stage_overrides.{stage_id} hooks.on_reviewer_passed",
            )


def _merge_workflow(
    base: dict[str, Any], overlay: dict[str, Any], *, overlay_path: Path
) -> dict[str, Any]:
    result = copy.deepcopy(base)
    extra = copy.deepcopy(overlay)
    extra.pop("reuse", None)
    reject_unknown_keys(extra, TOP_LEVEL_KEYS, str(overlay_path))
    if "id" in extra:
        result["id"] = extra["id"]
    if "capabilities" in extra:
        result["capabilities"] = list(extra["capabilities"] or [])
    for key in ("runtime_spec", "max_attempts"):
        if key in extra:
            result[key] = extra[key]
    if "registry" in extra:
        result.setdefault("registry", {})
        overlay_registry = extra["registry"] or {}
        reject_unknown_keys(
            overlay_registry, REGISTRY_KEYS, f"{overlay_path}: registry"
        )
        if "rules" in overlay_registry:
            result["registry"].setdefault("rules", {}).update(
                overlay_registry["rules"] or {}
            )
        if "tools" in overlay_registry:
            result["registry"].setdefault("tools", {}).update(
                overlay_registry["tools"] or {}
            )
        if "knowledge" in overlay_registry:
            result["registry"].setdefault("knowledge", {}).update(
                overlay_registry["knowledge"] or {}
            )
    if "hooks" in extra:
        result.setdefault("hooks", {})
        hooks_extra = extra["hooks"] or {}
        reject_unknown_keys(hooks_extra, HOOKS_KEYS, f"{overlay_path}: hooks")
        if "on_reviewer_passed" in hooks_extra:
            result["hooks"]["on_reviewer_passed"] = merge_list_declarations(
                result["hooks"].get("on_reviewer_passed"),
                hooks_extra.get("on_reviewer_passed"),
            )
    if "defaults" in extra:
        result.setdefault("defaults", {})
        defaults_extra = extra["defaults"] or {}
        reject_unknown_keys(defaults_extra, DEFAULTS_KEYS, f"{overlay_path}: defaults")
        if "rules" in defaults_extra:
            result["defaults"]["rules"] = list(defaults_extra["rules"] or [])
        if "knowledge" in defaults_extra:
            result["defaults"]["knowledge"] = list(defaults_extra["knowledge"] or [])
    if "assignments" in extra:
        result.setdefault("assignments", {})
        for assignment_id, spec in (extra["assignments"] or {}).items():
            if not isinstance(spec, dict):
                raise ValueError(
                    f"{overlay_path}: assignment {assignment_id} must be a mapping"
                )
            reject_unknown_keys(
                spec, ASSIGNMENT_KEYS, f"{overlay_path}: assignment {assignment_id}"
            )
            if assignment_id not in result["assignments"]:
                result["assignments"][assignment_id] = copy.deepcopy(spec)
            else:
                result["assignments"][assignment_id] = _merge_assignment(
                    result["assignments"][assignment_id],
                    spec,
                    label=f"{overlay_path}: assignment {assignment_id}",
                )
    if "stages" in extra:
        result["stages"] = copy.deepcopy(extra["stages"])
    _apply_stage_overrides(
        result, extra.get("stage_overrides") or {}, overlay_path=overlay_path
    )
    return result


def _merge_assignment(
    base: dict[str, Any], overlay: dict[str, Any], *, label: str
) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in overlay.items():
        if key in {"rules", "tools", "knowledge"}:
            merged[key] = merge_list_declarations(merged.get(key), value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _apply_stage_overrides(
    result: dict[str, Any], overrides: dict[str, Any], *, overlay_path: Path
) -> None:
    if not overrides:
        return
    stages = result.get("stages") or []
    by_id = {stage.get("id"): stage for stage in stages if isinstance(stage, dict)}
    for stage_id, patch in overrides.items():
        if stage_id not in by_id:
            raise ValueError(
                f"{overlay_path}: stage_overrides unknown stage {stage_id!r}"
            )
        if not isinstance(patch, dict):
            raise ValueError(
                f"{overlay_path}: stage_overrides {stage_id} must be a mapping"
            )
        reject_unknown_keys(
            patch, STAGE_OVERRIDE_KEYS, f"{overlay_path}: stage_overrides.{stage_id}"
        )
        stage = by_id[stage_id]
        if "spec" in patch:
            stage["spec"] = patch["spec"]
        if "max_attempts" in patch:
            stage["max_attempts"] = patch["max_attempts"]
        if "spec_additions" in patch:
            existing = list(stage.get("spec_additions") or [])
            for item in patch["spec_additions"] or []:
                if item not in existing:
                    existing.append(item)
            stage["spec_additions"] = existing
        if "steps" in patch:
            stage["steps"] = copy.deepcopy(patch["steps"])
        if "outputs" in patch:
            stage["outputs"] = copy.deepcopy(patch["outputs"])
        if "checks" in patch:
            stage["checks"] = copy.deepcopy(patch["checks"])
        for list_key in ("knowledge", "rules", "tools"):
            if list_key in patch:
                stage[list_key] = merge_list_declarations(
                    stage.get(list_key), patch[list_key]
                )
        if "hooks" in patch:
            hooks_patch = patch["hooks"] or {}
            if not isinstance(hooks_patch, dict):
                raise ValueError(
                    f"{overlay_path}: stage_overrides.{stage_id} hooks must be a mapping"
                )
            reject_unknown_keys(
                hooks_patch,
                HOOKS_KEYS,
                f"{overlay_path}: stage_overrides.{stage_id} hooks",
            )
            if "on_reviewer_passed" in hooks_patch:
                existing_hooks = stage.get("hooks") or {}
                if not isinstance(existing_hooks, dict):
                    existing_hooks = {}
                existing_hooks = dict(existing_hooks)
                existing_hooks["on_reviewer_passed"] = merge_list_declarations(
                    existing_hooks.get("on_reviewer_passed"),
                    hooks_patch.get("on_reviewer_passed"),
                )
                stage["hooks"] = existing_hooks
        if "context" in patch:
            stage["context"] = copy.deepcopy(patch["context"])


def _parse_workflow(raw: dict[str, Any], *, source_path: Path) -> Workflow:
    reject_unknown_keys(raw, TOP_LEVEL_KEYS, str(source_path))
    workflow_id = require_identifier(str(raw.get("id") or ""), label="workflow id")
    raw_caps = raw.get("capabilities") or []
    if not isinstance(raw_caps, list):
        raise ValueError(f"{source_path}: capabilities must be a list")
    capability_ids = [
        require_identifier(str(item), label="capability id") for item in raw_caps
    ]
    for item in raw_caps:
        if not isinstance(item, str):
            raise ValueError(
                f"{source_path}: capabilities items must be strings, got {item!r}"
            )
    registry = raw.get("registry") or {}
    reject_unknown_keys(registry, REGISTRY_KEYS, f"{source_path}: registry")
    rules = {}
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
        kind = str(spec.get("kind") or "local_dir")
        provider = require_identifier(
            str(spec.get("provider") or "local_files"), label="provider id"
        )
        knowledge[kid] = KnowledgeSource(
            knowledge_id=kid,
            kind=kind,
            path=require_relative_path(
                str(spec.get("path") or ""), label=f"knowledge {kid} path"
            ),
            provider=provider,
        )
    tools: dict[str, ToolSpec] = {}
    for tool_id, spec in dict(registry.get("tools") or {}).items():
        if not isinstance(spec, dict):
            raise ValueError(f"{source_path}: tool {tool_id} must be a mapping")
        reject_unknown_keys(spec, TOOL_KEYS, f"{source_path}: tool {tool_id}")
        tid = require_identifier(str(tool_id), label="tool id")
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
        )
    defaults = raw.get("defaults") or {}
    reject_unknown_keys(defaults, DEFAULTS_KEYS, f"{source_path}: defaults")
    hooks_raw = raw.get("hooks") or {}
    reject_unknown_keys(hooks_raw, HOOKS_KEYS, f"{source_path}: hooks")
    if "on_reviewer_passed" in hooks_raw:
        _ = parse_optional_list_field(hooks_raw.get("on_reviewer_passed"))

    reviewer_passed_hooks = [
        require_identifier(str(item), label="hook id")
        for item in resolve_list([], hooks_raw.get("on_reviewer_passed"))
    ]
    assignments: dict[str, Assignment] = {}
    for assignment_id, spec in dict(raw.get("assignments") or {}).items():
        if not isinstance(spec, dict):
            raise ValueError(
                f"{source_path}: assignment {assignment_id} must be a mapping"
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
        tools_decl = None
        if "tools" in spec:
            tools_decl = parse_optional_list_field(spec.get("tools"))
        rules_decl = None
        if "rules" in spec:
            rules_decl = parse_optional_list_field(spec.get("rules"))
        knowledge_decl = None
        if "knowledge" in spec:
            knowledge_decl = parse_optional_list_field(spec.get("knowledge"))
        task_spec = str(spec.get("task_spec") or "")
        if task_spec:
            task_spec = require_relative_path(task_spec, label=f"{aid} task_spec")
        assignments[aid] = Assignment(
            assignment_id=aid,
            role=role,
            task_spec=task_spec,
            tools_decl=tools_decl,
            rules_decl=rules_decl,
            knowledge_decl=knowledge_decl,
        )
    stages: list[Stage] = []
    if "max_attempts" in raw:
        default_attempts = _require_positive_int(
            raw.get("max_attempts"), label=f"{source_path}: max_attempts"
        )
    else:
        default_attempts = 3
    seen_stage_ids: set[str] = set()
    for spec in raw.get("stages") or []:
        if not isinstance(spec, dict):
            raise ValueError(f"{source_path}: each stage must be a mapping")
        reject_unknown_keys(spec, STAGE_KEYS, f"{source_path}: stage")
        stage_id = require_identifier(str(spec.get("id") or ""), label="stage id")
        if stage_id in seen_stage_ids:
            raise ValueError(f"{source_path}: duplicate stage id {stage_id}")
        seen_stage_ids.add(stage_id)
        steps: list[str] = []
        for step in spec.get("steps") or []:
            if isinstance(step, dict) and step.get("assignment"):
                steps.append(
                    require_identifier(str(step["assignment"]), label="assignment id")
                )
            else:
                steps.append(require_identifier(str(step), label="assignment id"))
        stage_knowledge = None
        if "knowledge" in spec:
            stage_knowledge = parse_optional_list_field(spec.get("knowledge"))
        stage_rules = None
        if "rules" in spec:
            stage_rules = parse_optional_list_field(spec.get("rules"))
        stage_tools = None
        if "tools" in spec:
            stage_tools = parse_optional_list_field(spec.get("tools"))
        stage_hooks_decl = None
        stage_hooks = spec.get("hooks")
        if isinstance(stage_hooks, dict):
            reject_unknown_keys(
                stage_hooks, HOOKS_KEYS, f"{source_path}: stage {stage_id} hooks"
            )
            if "on_reviewer_passed" in stage_hooks:
                stage_hooks_decl = parse_optional_list_field(
                    stage_hooks.get("on_reviewer_passed")
                )
        context = _parse_context(
            spec.get("context"), label=f"{source_path}: stage {stage_id} context"
        )
        if "max_attempts" in spec:
            stage_attempts = _require_positive_int(
                spec.get("max_attempts"),
                label=f"{source_path}: stage {stage_id} max_attempts",
            )
        else:
            stage_attempts = default_attempts
        outputs_raw = spec.get("outputs") or []
        additions_raw = spec.get("spec_additions") or []
        stages.append(
            Stage(
                stage_id=stage_id,
                spec=require_relative_path(
                    str(spec.get("spec") or ""), label=f"{stage_id} spec"
                ),
                max_attempts=stage_attempts,
                steps=steps,
                spec_additions=[
                    require_relative_path(str(item), label=f"{stage_id} spec_addition")
                    for item in _require_str_list(
                        additions_raw, label=f"{stage_id} spec_additions"
                    )
                ],
                outputs=[
                    require_workspace_output(str(item), label=f"{stage_id} output")
                    for item in _require_str_list(
                        outputs_raw, label=f"{stage_id} outputs"
                    )
                ],
                checks=_parse_checks(spec.get("checks"), source_path=source_path),
                knowledge_decl=stage_knowledge,
                rules_decl=stage_rules,
                tools_decl=stage_tools,
                reviewer_passed_hooks_decl=stage_hooks_decl,
                context=context,
            )
        )
    return Workflow(
        workflow_id=workflow_id,
        runtime_spec=require_relative_path(
            str(raw.get("runtime_spec") or ""), label="runtime_spec"
        ),
        max_attempts=default_attempts,
        rules=rules,
        tools=tools,
        knowledge=knowledge,
        default_rules=[str(item) for item in defaults.get("rules") or []],
        default_knowledge=[str(item) for item in defaults.get("knowledge") or []],
        stages=stages,
        assignments=assignments,
        source_path=source_path,
        reviewer_passed_hooks=reviewer_passed_hooks,
        capability_ids=capability_ids,
    )


def _parse_context(raw: Any, *, label: str) -> dict[str, object]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a mapping")
    return _validate_context_tree(raw, label=label)


def _validate_context_tree(obj: Any, *, label: str) -> dict[str, object]:
    if not isinstance(obj, dict):
        raise ValueError(f"{label} must be a mapping")
    result: dict[str, object] = {}
    for key, value in obj.items():
        require_identifier(str(key), label=f"{label} key")
        if isinstance(value, dict):
            result[str(key)] = _validate_context_tree(value, label=f"{label}.{key}")
        elif isinstance(value, (str, int, float, bool)) or value is None:
            result[str(key)] = value
        elif isinstance(value, list):
            cleaned = []
            for item in value:
                if isinstance(item, dict):
                    cleaned.append(
                        _validate_context_tree(item, label=f"{label}.{key}[]")
                    )
                elif isinstance(item, (str, int, float, bool)) or item is None:
                    cleaned.append(item)
                else:
                    raise ValueError(f"{label}.{key}: unsupported context value")
            result[str(key)] = cleaned
        else:
            raise ValueError(f"{label}.{key}: unsupported context value")
    return result


def _parse_tool_runtime(spec: dict[str, Any], *, label: str) -> ToolRuntimeSpec | None:
    raw = spec.get("runtime")
    if not raw or not isinstance(raw, dict):
        return None
    reject_unknown_keys(raw, TOOL_RUNTIME_KEYS, f"{label}.runtime")
    prefix = raw.get("env_prefix")
    return ToolRuntimeSpec(
        run_context_env=_require_bool(
            raw.get("run_context_env", False),
            label=f"{label}.runtime.run_context_env",
        )
        if "run_context_env" in raw
        else False,
        context_file=_require_bool(
            raw.get("context_file", False),
            label=f"{label}.runtime.context_file",
        )
        if "context_file" in raw
        else False,
        context_file_flag=str(raw.get("context_file_flag") or "--context-file"),
        env_prefix=str(prefix) if prefix is not None else None,
    )


def _parse_checks(raw: Any, *, source_path: Path) -> list[CheckRef]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{source_path}: checks must be a list")
    checks: list[CheckRef] = []
    for item in raw:
        if not isinstance(item, dict) or "id" not in item:
            raise ValueError(f"{source_path}: each check must declare id")
        reject_unknown_keys(item, CHECK_KEYS, f"{source_path}: check")
        checks.append(
            CheckRef(checker_id=require_identifier(str(item["id"]), label="checker id"))
        )
    return checks


def _validate_files(workflow: Workflow, project_root: Path) -> None:
    if not workflow.workflow_id:
        raise ValueError("workflow id is required")
    if not workflow.stages:
        raise ValueError("workflow must declare stages")
    _require_file(project_root, workflow.runtime_spec)
    for rule_id, relative in workflow.rules.items():
        _require_file(project_root, relative, label=f"rule {rule_id}")
    for knowledge_id, source in workflow.knowledge.items():
        if not source.path:
            raise ValueError(f"knowledge {knowledge_id} path is empty")
        path = _resolve(project_root, source.path)
        if source.kind == "local_dir":
            if not path.is_dir():
                raise FileNotFoundError(
                    f"missing knowledge dir {knowledge_id}: {source.path}"
                )
        elif not path.is_file():
            raise FileNotFoundError(f"missing knowledge {knowledge_id}: {source.path}")
    for kid in workflow.default_knowledge:
        if kid not in workflow.knowledge:
            raise ValueError(f"defaults: unknown knowledge {kid}")
    for assignment in workflow.assignments.values():
        _require_file(
            project_root, assignment.task_spec, label=assignment.assignment_id
        )
    for stage in workflow.stages:
        if not stage.stage_id:
            raise ValueError("stage id is required")
        _require_file(project_root, stage.spec, label=stage.stage_id)
        for addition in stage.spec_additions:
            _require_file(project_root, addition, label=f"{stage.stage_id} addition")
        if not stage.steps:
            raise ValueError(f"{stage.stage_id}: steps must not be empty")
        for assignment_id in stage.steps:
            if assignment_id not in workflow.assignments:
                raise ValueError(
                    f"{stage.stage_id}: unknown assignment {assignment_id}"
                )
    for tool in workflow.tools.values():
        for rule_id in tool.rules:
            if rule_id not in workflow.rules:
                raise ValueError(f"tool {tool.tool_id}: unknown rule {rule_id}")


def _require_file(project_root: Path, relative: str, label: str | None = None) -> None:
    if not relative:
        raise ValueError(f"{label or 'path'} is empty")
    path = _resolve(project_root, relative)
    if not path.is_file():
        raise FileNotFoundError(f"missing {label or relative}: {relative}")


def _resolve(project_root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        return path
    return project_root / path


def assignment_rule_ids(workflow: Workflow, assignment: Assignment) -> list[str]:
    bundle = workflow.bundles.get(assignment.assignment_id)
    if bundle is not None:
        return list(bundle.rule_ids)
    raise KeyError(f"no resolved bundle for {assignment.assignment_id}")
