"""Validate and resolve Workflow into per-assignment TaskBundles."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness.tools.lca_artifacts.checks import PROFILES

from .bundle import KnowledgeBinding, TaskBundle
from .handoff import WRITER_ROLES
from .lists import resolve_list
from .models import Assignment, Stage, Workflow


def resolve_workflow(workflow: Workflow) -> dict[str, TaskBundle]:
    stage_ids = [stage.stage_id for stage in workflow.stages]
    if len(stage_ids) != len(set(stage_ids)):
        raise ValueError("duplicate stage id in workflow")
    bundles: dict[str, TaskBundle] = {}
    for stage in workflow.stages:
        stage_knowledge = resolve_list(
            list(workflow.default_knowledge), stage.knowledge_decl
        )
        for assignment_id in stage.steps:
            assignment = workflow.assignments[assignment_id]
            bundle = _resolve_assignment(workflow, stage, assignment, stage_knowledge)
            bundles[assignment_id] = bundle
    return bundles


def resolve_bundle(workflow: Workflow, stage_id: str, assignment_id: str) -> TaskBundle:
    bundles = workflow.bundles or resolve_workflow(workflow)
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
    }


def _resolve_assignment(
    workflow: Workflow,
    stage: Stage,
    assignment: Assignment,
    stage_knowledge: list[str],
) -> TaskBundle:
    if not assignment.task_spec:
        raise ValueError(f"{assignment.assignment_id}: task_spec is required")
    knowledge_ids = resolve_list(stage_knowledge, assignment.knowledge_decl)
    for kid in knowledge_ids:
        if kid not in workflow.knowledge:
            raise ValueError(f"{assignment.assignment_id}: unknown knowledge {kid}")
    for check in stage.checks:
        if check.profile not in PROFILES:
            raise ValueError(
                f"{stage.stage_id}: unknown check profile {check.profile!r}"
            )
    rule_ids = _assignment_rule_ids(workflow, assignment)
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
        tool_ids=list(assignment.tools),
        knowledge_ids=knowledge_ids,
        knowledge_sources=knowledge_sources,
        expected_outputs=expected_outputs,
        checks=list(stage.checks),
    )


def _assignment_rule_ids(workflow: Workflow, assignment: Assignment) -> list[str]:
    ordered: list[str] = []
    for rule_id in [*workflow.default_rules, *assignment.rules]:
        if rule_id not in workflow.rules:
            raise ValueError(f"{assignment.assignment_id}: unknown rule {rule_id}")
        if rule_id not in ordered:
            ordered.append(rule_id)
    for tool_id in assignment.tools:
        if tool_id not in workflow.tools:
            raise ValueError(f"{assignment.assignment_id}: unknown tool {tool_id}")
        for rule_id in workflow.tools[tool_id].rules:
            if rule_id not in workflow.rules:
                raise ValueError(f"{assignment.assignment_id}: unknown rule {rule_id}")
            if rule_id not in ordered:
                ordered.append(rule_id)
    return ordered


def attach_bundles(workflow: Workflow, project_root: Path) -> None:
    bundles = resolve_workflow(workflow)
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
                path = _resolve(project_root, binding.path)
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
    path = _resolve(project_root, relative)
    if not path.is_file():
        raise FileNotFoundError(f"missing {label or relative}: {relative}")


def _resolve(project_root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        return path
    return project_root / path
