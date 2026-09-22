"""Validate and resolve Workflow into per-assignment TaskBundles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.workflows.runtime.capabilities import HarnessCapabilities
from scripts.workflows.runtime.identifiers import resolve_project_path

from ..loop.handoff import WRITER_ROLES
from .bundle import KnowledgeBinding, TaskBundle
from .lists import resolve_list
from .models import Assignment, Stage, Workflow


def resolve_workflow(
    workflow: Workflow, capabilities: HarnessCapabilities
) -> dict[str, TaskBundle]:
    stage_ids = [stage.stage_id for stage in workflow.stages]
    if len(stage_ids) != len(set(stage_ids)):
        raise ValueError("duplicate stage id in workflow")
    bundles: dict[str, TaskBundle] = {}
    for stage in workflow.stages:
        _validate_stage_topology(workflow, stage)
        _reject_duplicate_ids(
            [check.checker_id for check in stage.checks],
            label=f"{stage.stage_id}: checks",
        )
        stage_knowledge = resolve_list(
            list(workflow.default_knowledge), stage.knowledge_decl
        )
        stage_rules = resolve_list(list(workflow.default_rules), stage.rules_decl)
        stage_tools = resolve_list([], stage.tools_decl)
        stage_hooks = resolve_list(
            list(workflow.reviewer_passed_hooks), stage.reviewer_passed_hooks_decl
        )
        _reject_duplicate_ids(stage_hooks, label=f"{stage.stage_id}: hooks")
        for hook_id in stage_hooks:
            if hook_id not in capabilities.hooks.known_ids():
                raise ValueError(f"{stage.stage_id}: unknown hook {hook_id}")
        for assignment_id in stage.steps:
            assignment = workflow.assignments[assignment_id]
            bundle = _resolve_assignment(
                workflow,
                stage,
                assignment,
                stage_knowledge,
                stage_rules,
                stage_tools,
                stage_hooks,
                capabilities,
            )
            bundles[assignment_id] = bundle
    return bundles


def resolve_bundle(
    workflow: Workflow,
    stage_id: str,
    assignment_id: str,
    *,
    capabilities: HarnessCapabilities | None = None,
) -> TaskBundle:
    if workflow.bundles:
        bundle = workflow.bundles.get(assignment_id)
        if bundle is None or bundle.stage_id != stage_id:
            raise KeyError(f"no bundle for {stage_id}/{assignment_id}")
        return bundle
    if capabilities is None:
        raise ValueError("capabilities required when workflow.bundles is empty")
    bundles = resolve_workflow(workflow, capabilities)
    bundle = bundles.get(assignment_id)
    if bundle is None or bundle.stage_id != stage_id:
        raise KeyError(f"no bundle for {stage_id}/{assignment_id}")
    return bundle


def diagnose_assignment(
    workflow: Workflow,
    stage_id: str,
    assignment_id: str,
) -> dict[str, Any]:
    bundle = resolve_bundle(workflow, stage_id, assignment_id)
    return {
        "assignment_id": bundle.assignment_id,
        "stage_id": bundle.stage_id,
        "role": bundle.role,
        "specs": list(bundle.spec_paths),
        "rules": list(bundle.rule_ids),
        "tools": list(bundle.tool_ids),
        "knowledge": [item.to_dict() for item in bundle.knowledge_sources],
        "outputs": list(bundle.expected_outputs),
        "checks": [item.to_dict() for item in bundle.checks],
        "reviewer_passed_hooks": list(bundle.reviewer_passed_hooks),
    }


def _resolve_assignment(
    workflow: Workflow,
    stage: Stage,
    assignment: Assignment,
    stage_knowledge: list[str],
    stage_rules: list[str],
    stage_tools: list[str],
    stage_hooks: list[str],
    capabilities: HarnessCapabilities,
) -> TaskBundle:
    if not assignment.task_spec:
        raise ValueError(f"{assignment.assignment_id}: task_spec is required")
    knowledge_ids = resolve_list(stage_knowledge, assignment.knowledge_decl)
    tool_ids = resolve_list(stage_tools, assignment.tools_decl)
    base_rules = resolve_list(stage_rules, assignment.rules_decl)
    _reject_duplicate_ids(knowledge_ids, label=f"{assignment.assignment_id}: knowledge")
    _reject_duplicate_ids(tool_ids, label=f"{assignment.assignment_id}: tools")
    for kid in knowledge_ids:
        if kid not in workflow.knowledge:
            raise ValueError(f"{assignment.assignment_id}: unknown knowledge {kid}")
        provider = workflow.knowledge[kid].provider
        if provider not in capabilities.knowledge.known_ids():
            raise ValueError(
                f"{assignment.assignment_id}: unknown knowledge provider {provider}"
            )
    for check in stage.checks:
        if check.checker_id not in capabilities.checkers.known_ids():
            raise ValueError(f"{stage.stage_id}: unknown checker {check.checker_id!r}")
    for tool_id in tool_ids:
        if tool_id not in workflow.tools:
            raise ValueError(f"{assignment.assignment_id}: unknown tool {tool_id}")
    rule_ids = _finalize_rule_ids(
        workflow, assignment.assignment_id, base_rules, tool_ids
    )
    spec_paths = [
        workflow.runtime_spec,
        stage.spec,
        *stage.spec_additions,
        assignment.task_spec,
    ]
    expected_outputs = list(stage.outputs) if assignment.role in WRITER_ROLES else []
    knowledge_sources = [
        KnowledgeBinding(
            knowledge_id=kid,
            kind=workflow.knowledge[kid].kind,
            path=workflow.knowledge[kid].path,
            provider=workflow.knowledge[kid].provider,
        )
        for kid in knowledge_ids
    ]
    return TaskBundle(
        workflow_id=workflow.workflow_id,
        stage_id=stage.stage_id,
        assignment_id=assignment.assignment_id,
        role=assignment.role,
        max_attempts=stage.max_attempts,
        runtime_spec=workflow.runtime_spec,
        spec_paths=spec_paths,
        rule_ids=rule_ids,
        tool_ids=tool_ids,
        knowledge_ids=knowledge_ids,
        knowledge_sources=knowledge_sources,
        expected_outputs=expected_outputs,
        checks=list(stage.checks),
        reviewer_passed_hooks=list(stage_hooks),
        context=dict(stage.context),
    )


def _validate_stage_topology(workflow: Workflow, stage: Stage) -> None:
    if not stage.steps:
        raise ValueError(f"{stage.stage_id}: steps must not be empty")
    roles = []
    for assignment_id in stage.steps:
        if assignment_id not in workflow.assignments:
            raise ValueError(f"{stage.stage_id}: unknown assignment {assignment_id}")
        roles.append(workflow.assignments[assignment_id].role)
    if len(roles) == 1 and roles[0] == "reviewer":
        if stage.checks:
            raise ValueError(
                f"{stage.stage_id}: review-only stage must not declare checks"
            )
        return
    if len(roles) == 2 and roles[0] in WRITER_ROLES and roles[1] == "reviewer":
        return
    raise ValueError(
        f"{stage.stage_id}: unsupported stage topology {roles}; "
        "expected review-only [reviewer] or reviewed [writer, reviewer]"
    )


def _reject_duplicate_ids(values: list[str], *, label: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"{label}: duplicate id {value}")
        seen.add(value)


def _finalize_rule_ids(
    workflow: Workflow,
    assignment_id: str,
    base_rules: list[str],
    tool_ids: list[str],
) -> list[str]:
    ordered: list[str] = []
    for rule_id in base_rules:
        if rule_id not in workflow.rules:
            raise ValueError(f"{assignment_id}: unknown rule {rule_id}")
        if rule_id not in ordered:
            ordered.append(rule_id)
    for tool_id in tool_ids:
        for rule_id in workflow.tools[tool_id].rules:
            if rule_id not in workflow.rules:
                raise ValueError(f"{assignment_id}: unknown rule {rule_id}")
            if rule_id not in ordered:
                ordered.append(rule_id)
    return ordered


def attach_bundles(
    workflow: Workflow,
    project_root: Path,
    capabilities: HarnessCapabilities,
) -> None:
    bundles = resolve_workflow(workflow, capabilities)
    workflow.bundles = bundles
    _validate_bundle_files(workflow, project_root)


def _validate_bundle_files(workflow: Workflow, project_root: Path) -> None:
    seen_assignments: set[str] = set()
    for stage in workflow.stages:
        for assignment_id in stage.steps:
            if assignment_id in seen_assignments:
                raise ValueError(f"duplicate assignment id {assignment_id}")
            seen_assignments.add(assignment_id)
            bundle = workflow.bundles[assignment_id]
            for relative in bundle.spec_paths:
                _require_file(project_root, relative, label=assignment_id)
            for rule_id in bundle.rule_ids:
                _require_file(
                    project_root, workflow.rules[rule_id], label=f"rule {rule_id}"
                )
            for binding in bundle.knowledge_sources:
                path = resolve_project_path(
                    project_root, binding.path, label=binding.knowledge_id
                )
                if binding.kind == "local_dir":
                    if not path.is_dir():
                        raise FileNotFoundError(
                            f"missing knowledge dir {binding.knowledge_id}: {binding.path}"
                        )
                else:
                    _require_file(
                        project_root, binding.path, label=binding.knowledge_id
                    )


def _require_file(project_root: Path, relative: str, label: str | None = None) -> None:
    if not relative:
        raise ValueError(f"{label or 'path'} is empty")
    path = resolve_project_path(project_root, relative, label=label or relative)
    if not path.is_file():
        raise FileNotFoundError(f"missing {label or relative}: {relative}")
