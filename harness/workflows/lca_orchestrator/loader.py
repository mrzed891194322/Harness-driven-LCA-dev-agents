"""Load and merge workflow YAML."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from .models import Assignment, Stage, ToolSpec, Workflow

FORBIDDEN_PROMPT_KEYS = frozenset({"prompt", "extra_prompt"})


def load_workflow(path: Path, *, project_root: Path) -> Workflow:
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
    if "defaults" in extra:
        result.setdefault("defaults", {})
        if extra["defaults"] and "rules" in extra["defaults"]:
            result["defaults"]["rules"] = list(extra["defaults"]["rules"] or [])
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


def _parse_workflow(raw: dict[str, Any], *, source_path: Path) -> Workflow:
    registry = raw.get("registry") or {}
    rules = {str(k): str(v) for k, v in dict(registry.get("rules") or {}).items()}
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
        )
    defaults = raw.get("defaults") or {}
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
        assignments[str(assignment_id)] = Assignment(
            assignment_id=str(assignment_id),
            role=role,
            task_spec=str(spec.get("task_spec") or ""),
            tools=[str(item) for item in spec.get("tools") or []],
            rules=[str(item) for item in spec.get("rules") or []],
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
        stages.append(
            Stage(
                stage_id=str(spec.get("id") or ""),
                spec=str(spec.get("spec") or ""),
                max_attempts=int(spec.get("max_attempts") or default_attempts),
                steps=steps,
                spec_additions=[str(item) for item in spec.get("spec_additions") or []],
            )
        )
    return Workflow(
        workflow_id=str(raw.get("id") or ""),
        runtime_spec=str(raw.get("runtime_spec") or ""),
        max_attempts=default_attempts,
        rules=rules,
        tools=tools,
        default_rules=[str(item) for item in defaults.get("rules") or []],
        stages=stages,
        assignments=assignments,
        source_path=source_path,
    )


def _validate_files(workflow: Workflow, project_root: Path) -> None:
    if not workflow.workflow_id:
        raise ValueError("workflow id is required")
    if not workflow.stages:
        raise ValueError("workflow must declare stages")
    _require_file(project_root, workflow.runtime_spec)
    for rule_id, relative in workflow.rules.items():
        _require_file(project_root, relative, label=f"rule {rule_id}")
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
    ordered: list[str] = []
    for rule_id in [*workflow.default_rules, *assignment.rules]:
        if rule_id not in ordered:
            ordered.append(rule_id)
    for tool_id in assignment.tools:
        for rule_id in workflow.tools[tool_id].rules:
            if rule_id not in ordered:
                ordered.append(rule_id)
    return ordered
