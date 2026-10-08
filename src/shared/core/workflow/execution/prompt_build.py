"""Assemble worker prompt from TaskBundle and runtime context."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config.bundle import TaskBundle

_RUNTIME_PROTOCOL = """\
# 通用运行协议
你是主编排器调度的 worker。只完成本 assignment；不要推进阶段、不要改检查点或 manifest。
必须按 handoff 契约向运行上下文中的 handoff_path 提交结果（无 handoff 文件等于未交卷）。
字段：schema_version=1, role, stage, attempt, status, status_reason, fix_instructions, artifacts。
写者 status：ok / failed / blocked；审查者 status：passed / failed。
failed/blocked 也必须写入 handoff 并给出非空 status_reason。
若运行上下文的 fix_instructions 指向 handoff 契约错误：只改写当前 handoff JSON，不要擅自改产物。
确定性验收由主机根据 stage spec 调用已注册的 stdio MCP 完成；文件存在本身不证明任务完成。
"""


def build_prompt(
    bundle: TaskBundle,
    *,
    project_root: Path,
    rules: dict[str, str],
    run_context: dict[str, Any],
) -> str:
    context = dict(run_context)
    if bundle.knowledge_sources:
        context["knowledge_sources"] = [
            item.to_dict() for item in bundle.knowledge_sources
        ]
    spec_summary = {
        "id": bundle.stage_spec.spec_id,
        "source": bundle.stage_spec.source_path,
        "inputs": [
            {"path": item.path, "required": item.required}
            for item in bundle.stage_spec.inputs
        ],
        "outputs": [
            {
                "path": item.path,
                "required": item.required,
                "kind": item.kind,
                "format": item.format,
                "schema": item.schema,
            }
            for item in bundle.stage_spec.outputs
        ],
        "acceptance_checks": [item.to_dict() for item in bundle.acceptance_checks],
        "handoff_schema": bundle.stage_spec.handoff_schema,
    }
    parts: list[str] = [
        "# 运行上下文",
        json.dumps(context, ensure_ascii=False, indent=2),
        "",
        _RUNTIME_PROTOCOL.strip(),
        "",
        "# 阶段机器契约（摘要）",
        json.dumps(spec_summary, ensure_ascii=False, indent=2),
    ]
    for rule_id in bundle.rule_ids:
        parts.extend(
            [
                "",
                f"# 规则 {rule_id}",
                _read(project_root, rules[rule_id]),
            ]
        )
    parts.extend(
        [
            "",
            "# 本轮提交",
            "完成本轮的最后一动作为交卷（无 handoff 文件等于未交卷，主编排会协议返工）：",
            f"- 将 handoff JSON 写入与下列路径完全一致的位置：{run_context.get('handoff_path') or ''}",
            "（若已注入工具规则允许通过 MCP 提交 handoff，亦可使用该工具，路径仍由主机决定。）",
            "路径必须与运行上下文 handoff_path 完全一致。",
            "不要推进阶段、不要维护会话映射、不要改检查点或 manifest。",
        ]
    )
    return "\n".join(parts).strip() + "\n"


def _read(project_root: Path, relative: str) -> str:
    return (project_root / relative).read_text(encoding="utf-8").strip()
