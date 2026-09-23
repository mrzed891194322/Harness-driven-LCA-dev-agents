"""Assemble worker prompt from TaskBundle and runtime context."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config.bundle import TaskBundle


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
    parts: list[str] = [
        "# 运行上下文",
        json.dumps(context, ensure_ascii=False, indent=2),
        "",
        "# 公共任务协议",
        _read(project_root, bundle.runtime_spec),
    ]
    body_paths = bundle.spec_paths[1:]
    if body_paths:
        parts.extend(["", "# 阶段共有契约", _read(project_root, body_paths[0])])
        additions = body_paths[1:-1]
        for addition in additions:
            parts.extend(["", "# 本阶段补充契约", _read(project_root, addition)])
        parts.extend(["", "# 当前角色任务", _read(project_root, body_paths[-1])])
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
            "- 优先调用 lca_artifacts 的 submit_handoff（路径由主机决定）；或",
            f"- 将 handoff JSON 写入与下列路径完全一致的位置：{run_context.get('handoff_path') or ''}",
            "字段：schema_version=1, role, stage, attempt, status, status_reason, fix_instructions, artifacts。",
            "路径必须与运行上下文 handoff_path 完全一致；failed/blocked 也必须写入 handoff 并给出非空 status_reason。",
            "写者完成本阶段任务且产物已落盘后才提交 ok 和非空 status_reason；主编排随后执行配置的确定性检查，文件存在本身不证明任务完成。",
            "checks_ref、evidence_manifest_ref 若写入则必须是路径字符串，取工具返回的 .path，不要把 {path, sha256, size_bytes} 整段写入。",
            "executor / reviser status: ok / failed / blocked；reviewer status: passed / failed。",
            "若运行上下文的 fix_instructions 是 handoff 契约错误：只改写当前 handoff JSON，不要当成审查意见去改产物。",
            "不要推进阶段、不要维护会话映射、不要改检查点或 manifest。",
        ]
    )
    return "\n".join(parts).strip() + "\n"


def _read(project_root: Path, relative: str) -> str:
    return (project_root / relative).read_text(encoding="utf-8").strip()
