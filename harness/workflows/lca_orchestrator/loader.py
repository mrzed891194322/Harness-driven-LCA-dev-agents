"""Load and merge workflow YAML."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from harness.runtime.capabilities import HarnessCapabilities
from harness.runtime.tool_runtime import ToolRuntimeSpec

from .bundle import CheckRef
from .lists import parse_optional_list_field, resolve_list
from .models import Assignment, KnowledgeSource, Stage, ToolSpec, Workflow
from .resolve import attach_bundles

FORBIDDEN_PROMPT_KEYS = frozenset({"prompt", "extra_prompt"})


def load_workflow(
    path: Path,
    *,
    project_root: Path,
    capabilities: HarnessCapabilities | None = None,
) -> Workflow:
    raw = _read_yaml(path)
    _reject_prompt_fields(raw, path)
    if raw.get("reuse"):
        base_path = _resolve(project_root, str(raw["reuse"]))
        base_raw = _read_yaml(base_path)
        _reject_prompt_fields(base_raw, base_path)
        if base_raw.get("reuse"):
            raise ValueError(f"{path}: nested reuse is not supported")
        raw = _merge_workflow(base_raw, raw)
    workflow = _parse_workflow(raw, source_path=path)
    _validate_files(workflow, project_root)
    attach_bundles(workflow, project_root, capabilities)
    return workflow


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
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


def _merge_workflow(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    extra = copy.deepcopy(overlay)
    extra.pop("reuse", None)
    if "id" in extra:
        result["id"] = extra["id"]
    for key in ("runtime_spec", "max_attempts"):
        if key in extra:
            result[key] = extra[key]
    if "registry" in extra:
        result.setdefault("registry", {})
        overlay_registry = extra["registry"] or {}
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
        if "on_reviewer_passed" in hooks_extra:
            result["hooks"]["on_reviewer_passed"] = list(
                hooks_extra["on_reviewer_passed"] or []
            )
    if "defaults" in extra:
        result.setdefault("defaults", {})
        defaults_extra = extra["defaults"] or {}
        if "rules" in defaults_extra:
            result["defaults"]["rules"] = list(defaults_extra["rules"] or [])
        if "knowledge" in defaults_extra:
            result["defaults"]["knowledge"] = list(defaults_extra["knowledge"] or [])
    if "assignments" in extra:
        result.setdefault("assignments", {})
        for assignment_id, spec in (extra["assignments"] or {}).items():
            if assignment_id not in result["assignments"]:
                result["assignments"][assignment_id] = copy.deepcopy(spec)
            else:
                merged = copy.deepcopy(result["assignments"][assignment_id])
                merged.update(copy.deepcopy(spec) or {})
                result["assignments"][assignment_id] = merged
    if "stages" in extra:
        result["stages"] = copy.deepcopy(extra["stages"])
    _apply_stage_overrides(result, extra.get("stage_overrides") or {})
    return result


def _apply_stage_overrides(result: dict[str, Any], overrides: dict[str, Any]) -> None:
    if not overrides:
        return
    stages = result.get("stages") or []
    by_id = {stage.get("id"): stage for stage in stages if isinstance(stage, dict)}
    for stage_id, patch in overrides.items():
        if stage_id not in by_id or not isinstance(patch, dict):
            continue
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
        if "knowledge" in patch:
            stage["knowledge"] = copy.deepcopy(patch["knowledge"])


def _parse_workflow(raw: dict[str, Any], *, source_path: Path) -> Workflow:
    registry = raw.get("registry") or {}
    rules = {str(k): str(v) for k, v in dict(registry.get("rules") or {}).items()}
    knowledge: dict[str, KnowledgeSource] = {}
    for knowledge_id, spec in dict(registry.get("knowledge") or {}).items():
        if not isinstance(spec, dict):
            raise ValueError(
                f"{source_path}: knowledge {knowledge_id} must be a mapping"
            )
        kind = str(spec.get("kind") or "local_dir")
        knowledge[str(knowledge_id)] = KnowledgeSource(
            knowledge_id=str(knowledge_id),
            kind=kind,
            path=str(spec.get("path") or ""),
            provider=str(spec.get("provider") or "local_files"),
        )
    tools: dict[str, ToolSpec] = {}
    for tool_id, spec in dict(registry.get("tools") or {}).items():
        if not isinstance(spec, dict):
            raise ValueError(f"{source_path}: tool {tool_id} must be a mapping")
        tools[str(tool_id)] = ToolSpec(
            tool_id=str(tool_id),
            transport=str(spec.get("transport") or "stdio"),
            command=spec.get("command"),
            args=[str(item) for item in spec.get("args") or []],
            url=spec.get("url"),
            env={str(k): str(v) for k, v in dict(spec.get("env") or {}).items()},
            headers={
                str(k): str(v) for k, v in dict(spec.get("headers") or {}).items()
            },
            rules=[str(item) for item in spec.get("rules") or []],
            runtime=_parse_tool_runtime(spec),
        )
    defaults = raw.get("defaults") or {}
    hooks_raw = raw.get("hooks") or {}
    reviewer_passed_hooks = [
        str(item) for item in hooks_raw.get("on_reviewer_passed") or []
    ]
    assignments: dict[str, Assignment] = {}
    for assignment_id, spec in dict(raw.get("assignments") or {}).items():
        if not isinstance(spec, dict):
            raise ValueError(
                f"{source_path}: assignment {assignment_id} must be a mapping"
            )
        role = str(spec.get("role") or "")
        if role not in {"executor", "reviser", "reviewer"}:
            raise ValueError(
                f"{source_path}: assignment {assignment_id} has invalid role {role!r}"
            )
        knowledge_decl = None
        if "knowledge" in spec:
            knowledge_decl = parse_optional_list_field(spec.get("knowledge"))
        assignment_tools: list[str] = []
        if "tools" in spec:
            assignment_tools = resolve_list(
                [], parse_optional_list_field(spec.get("tools"))
            )
        assignment_rules: list[str] = []
        if "rules" in spec:
            assignment_rules = resolve_list(
                [], parse_optional_list_field(spec.get("rules"))
            )
        assignments[str(assignment_id)] = Assignment(
            assignment_id=str(assignment_id),
            role=role,
            task_spec=str(spec.get("task_spec") or ""),
            tools=assignment_tools,
            rules=assignment_rules,
            knowledge_decl=knowledge_decl,
        )
    stages: list[Stage] = []
    default_attempts = int(raw.get("max_attempts") or 3)
    for spec in raw.get("stages") or []:
        if not isinstance(spec, dict):
            raise ValueError(f"{source_path}: each stage must be a mapping")
        steps: list[str] = []
        for step in spec.get("steps") or []:
            if isinstance(step, dict) and step.get("assignment"):
                steps.append(str(step["assignment"]))
            else:
                steps.append(str(step))
        stage_knowledge = None
        if "knowledge" in spec:
            stage_knowledge = parse_optional_list_field(spec.get("knowledge"))
        stage_hooks_decl = None
        stage_hooks = spec.get("hooks")
        if isinstance(stage_hooks, dict) and "on_reviewer_passed" in stage_hooks:
            stage_hooks_decl = parse_optional_list_field(
                stage_hooks.get("on_reviewer_passed")
            )
        stages.append(
            Stage(
                stage_id=str(spec.get("id") or ""),
                spec=str(spec.get("spec") or ""),
                max_attempts=int(spec.get("max_attempts") or default_attempts),
                steps=steps,
                spec_additions=[str(item) for item in spec.get("spec_additions") or []],
                outputs=[str(item) for item in spec.get("outputs") or []],
                checks=_parse_checks(spec.get("checks"), source_path=source_path),
                knowledge_decl=stage_knowledge,
                reviewer_passed_hooks_decl=stage_hooks_decl,
            )
        )
    return Workflow(
        workflow_id=str(raw.get("id") or ""),
        runtime_spec=str(raw.get("runtime_spec") or ""),
        max_attempts=default_attempts,
        rules=rules,
        tools=tools,
        knowledge=knowledge,
        default_rules=[str(item) for item in defaults.get("rules") or []],
        default_knowledge=[str(item) for item in defaults.get("knowledge") or []],
        reviewer_passed_hooks=reviewer_passed_hooks,
        stages=stages,
        assignments=assignments,
        source_path=source_path,
    )


def _parse_tool_runtime(spec: dict[str, Any]) -> ToolRuntimeSpec | None:
    raw = spec.get("runtime")
    if not raw or not isinstance(raw, dict):
        return None
    return ToolRuntimeSpec(
        run_context_env=bool(raw.get("run_context_env")),
        context_file=bool(raw.get("context_file")),
        context_file_flag=str(raw.get("context_file_flag") or "--context-file"),
        env_prefix=str(raw.get("env_prefix") or "LCA"),
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
        checks.append(CheckRef(checker_id=str(item["id"])))
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
        for rule_id in assignment.rules:
            if rule_id not in workflow.rules:
                raise ValueError(f"{assignment.assignment_id}: unknown rule {rule_id}")
        for tool_id in assignment.tools:
            if tool_id not in workflow.tools:
                raise ValueError(f"{assignment.assignment_id}: unknown tool {tool_id}")
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
    ordered: list[str] = []
    for rule_id in [*workflow.default_rules, *assignment.rules]:
        if rule_id not in ordered:
            ordered.append(rule_id)
    for tool_id in assignment.tools:
        for rule_id in workflow.tools[tool_id].rules:
            if rule_id not in ordered:
                ordered.append(rule_id)
    return ordered
