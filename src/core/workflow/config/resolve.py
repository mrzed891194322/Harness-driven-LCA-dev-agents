"""Validate and resolve Workflow into per-assignment TaskBundles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.runtime.capabilities import HarnessCapabilities
from core.workflow.spec.loader import load_stage_spec

from ..execution.handoff import WRITER_ROLES
from .bundle import KnowledgeBinding, TaskBundle
from .lists import resolve_list
from .models import Assignment, Stage, Workflow


def resolve_workflow(
    workflow: Workflow, capabilities: HarnessCapabilities, *, project_root: Path
) -> dict[str, TaskBundle]:
    if not workflow.stages:
        raise ValueError("workflow must declare stages")
    for kid in workflow.default_knowledge:
        if kid not in workflow.knowledge:
            raise ValueError(f"defaults: unknown knowledge {kid}")
    for tool in workflow.tools.values():
        for rule_id in tool.rules:
            if rule_id not in workflow.rules:
                raise ValueError(f"tool {tool.tool_id}: unknown rule {rule_id}")
    stage_ids = [stage.stage_id for stage in workflow.stages]
    if len(stage_ids) != len(set(stage_ids)):
        raise ValueError("duplicate stage id in workflow")
    bundles: dict[str, TaskBundle] = {}
    for stage in workflow.stages:
        _validate_stage_topology(workflow, stage)
        stage_spec = load_stage_spec(
            project_root / stage.spec,
            project_root=project_root,
            relative=stage.spec,
        )
        if stage_spec.spec_id != stage.stage_id:
            raise ValueError(
                f"{stage.stage_id}: spec id {stage_spec.spec_id!r} does not match stage"
            )
        for check in stage_spec.acceptance_checks:
            if check.tool not in workflow.tools:
                raise ValueError(
                    f"{stage.stage_id}: acceptance check {check.id} "
                    f"references unknown tool {check.tool!r}"
                )
        for action in stage_spec.on_reviewer_passed:
            if action.tool not in workflow.tools:
                raise ValueError(
                    f"{stage.stage_id}: lifecycle action {action.id} "
                    f"references unknown tool {action.tool!r}"
                )
        for check in stage_spec.handoff_checks:
            if check.tool not in workflow.tools:
                raise ValueError(
                    f"{stage.stage_id}: handoff check {check.id} "
                    f"references unknown tool {check.tool!r}"
                )
        stage_knowledge = resolve_list(
            list(workflow.default_knowledge), stage.knowledge_decl
        )
        stage_rules = resolve_list(list(workflow.default_rules), stage.rules_decl)
        stage_tools = resolve_list([], stage.tools_decl)
        for assignment_id in stage.steps:
            if assignment_id in bundles:
                raise ValueError(f"duplicate assignment id {assignment_id}")
            assignment = workflow.assignments[assignment_id]
            bundles[assignment_id] = _resolve_assignment(
                workflow,
                stage,
                assignment,
                stage_spec,
                stage_knowledge,
                stage_rules,
                stage_tools,
                capabilities,
            )
    return bundles


def resolve_bundle(
    workflow: Workflow,
    stage_id: str,
    assignment_id: str,
    *,
    capabilities: HarnessCapabilities | None = None,
    project_root: Path | None = None,
) -> TaskBundle:
    if workflow.bundles:
        bundle = workflow.bundles.get(assignment_id)
        if bundle is None or bundle.stage_id != stage_id:
            raise KeyError(f"no bundle for {stage_id}/{assignment_id}")
        return bundle
    if capabilities is None or project_root is None:
        raise ValueError(
            "capabilities and project_root required when workflow.bundles is empty"
        )
    bundles = resolve_workflow(workflow, capabilities, project_root=project_root)
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
        "spec": bundle.stage_spec.source_path,
        "rules": list(bundle.rule_ids),
        "tools": list(bundle.tool_ids),
        "knowledge": [item.to_dict() for item in bundle.knowledge_sources],
        "outputs": list(bundle.expected_outputs),
        "acceptance_checks": [item.to_dict() for item in bundle.acceptance_checks],
        "on_reviewer_passed": [item.to_dict() for item in bundle.on_reviewer_passed],
    }


def _resolve_assignment(
    workflow: Workflow,
    stage: Stage,
    assignment: Assignment,
    stage_spec: Any,
    stage_knowledge: list[str],
    stage_rules: list[str],
    stage_tools: list[str],
    capabilities: HarnessCapabilities,
) -> TaskBundle:
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
    for tool_id in tool_ids:
        if tool_id not in workflow.tools:
            raise ValueError(f"{assignment.assignment_id}: unknown tool {tool_id}")
    rule_ids = _finalize_rule_ids(
        workflow, assignment.assignment_id, base_rules, tool_ids
    )
    expected_outputs = (
        list(stage_spec.output_paths()) if assignment.role in WRITER_ROLES else []
    )
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
        stage_spec=stage_spec,
        rule_ids=rule_ids,
        tool_ids=tool_ids,
        knowledge_ids=knowledge_ids,
        knowledge_sources=knowledge_sources,
        expected_outputs=expected_outputs,
        acceptance_checks=list(stage_spec.acceptance_checks),
        on_reviewer_passed=list(stage_spec.on_reviewer_passed),
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
        return
    if len(roles) == 2 and roles[0] in WRITER_ROLES and roles[1] == "reviewer":
        return
    raise ValueError(
        f"{stage.stage_id}: unsupported stage topology {roles}; "
        "expected review-only [reviewer] or reviewed [writer, reviewer]"
    )


def _reject_duplicate_ids(values: list[str], *, label: str, kind: str = "id") -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"{label}: duplicate {kind} {value}")
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
    workflow.bundles = resolve_workflow(
        workflow, capabilities, project_root=project_root
    )
