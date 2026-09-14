"""Assemble one worker turn input from spec, rules, and run context."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .loader import assignment_rule_ids
from .models import Assignment, Stage, Workflow


def assignment_spec_paths(
    workflow: Workflow,
    stage: Stage,
    assignment: Assignment,
) -> list[str]:
    """Return repo-relative spec paths for this assignment, in prompt order."""
    return [
        workflow.runtime_spec,
        stage.spec,
        *stage.spec_additions,
        assignment.task_spec,
    ]


def assemble_prompt(
    workflow: Workflow,
    *,
    project_root: Path,
    stage: Stage,
    assignment: Assignment,
    run_context: dict[str, Any],
) -> str:
    parts: list[str] = [
        "# 运行上下文",
        json.dumps(run_context, ensure_ascii=False, indent=2),
        "",
        "# 公共任务协议",
        _read(project_root, workflow.runtime_spec),
        "",
        "# 阶段共有契约",
        _read(project_root, stage.spec),
    ]
    for addition in stage.spec_additions:
        parts.extend(["", "# 本阶段补充契约", _read(project_root, addition)])
    parts.extend(
        [
            "",
            "# 当前角色任务",
            _read(project_root, assignment.task_spec),
        ]
    )
    for rule_id in assignment_rule_ids(workflow, assignment):
        parts.extend(
            [
                "",
                f"# 规则 {rule_id}",
                _read(project_root, workflow.rules[rule_id]),
            ]
        )
    parts.extend(
        [
            "",
            "# 本轮提交",
            "完成本轮后写入 handoff JSON：",
            str(run_context.get("handoff_path") or ""),
            "字段：schema_version=1, role, stage, attempt, status, status_reason, fix_instructions, artifacts。",
            "写者 ok 的充分条件是本轮产物已落盘且 status_reason 非空；不必自己先跑 validate_artifacts，主编排会在 handoff 后做确定性检查。",
            "checks_ref、evidence_manifest_ref 若写入则必须是路径字符串，取工具返回的 .path，不要把 {path, sha256, size_bytes} 整段写入。",
            "rework_scope: none/report_only/calculation_changed/model_changed。校验状态由工具生成。",
            "executor / reviser status: ok / failed / blocked；reviewer status: passed / failed。",
            "若运行上下文的 fix_instructions 是 handoff 契约错误：只改写当前 handoff JSON，不要当成审查意见去改 BOM 或其他产物。",
            "不要推进阶段、不要维护会话映射、不要改检查点或 manifest。",
        ]
    )
    return "\n".join(parts).strip() + "\n"


def _read(project_root: Path, relative: str) -> str:
    return (project_root / relative).read_text(encoding="utf-8").strip()
