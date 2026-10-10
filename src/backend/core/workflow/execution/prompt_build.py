"""Assemble the worker prompt from TaskBundle and runtime context.

Order (P5): run protocol -> rules prompts -> stage rules -> one-line submission
note. The machine contract (schemas, examples, acceptance) is NOT in the prompt:
the host injects ``get_spec()`` as the session's first context and spec_mcp is
the only delivery channel. Spec (machine constraints) beats rules on conflict.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.core.runtime import harness_fs

from ..config.bundle import TaskBundle

STAGE_RULES_PREFIX = "harness/rules/stages/"
SUBMISSION_NOTE = "以 spec_mcp 为准，用 submit 交付"

_RUNTIME_PROTOCOL = """\
# 通用运行协议
你是主编排器调度的 worker。只完成本 assignment；不要推进阶段、不要改检查点或 manifest。
交付与交卷只走 spec_mcp：get_spec 看规格，submit 交付物（失败时按错误清单修正后重交），status 看进度，最后 submit_handoff 交卷；无 handoff 等于未交卷。
写者 status：ok / failed / blocked；审查者 status：passed / failed。failed/blocked 也必须交卷并给出非空 status_reason。
写者 status=ok 时，spec_mcp 要求全部 required 交付物已通过 submit 验收。
若运行上下文的 fix_instructions 指向 handoff 契约错误：重新调用 submit_handoff 提交更正后的 handoff，不要擅自改产物。
spec（机器约束）与规则（提示词）冲突时，以 spec 为准。
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
    parts: list[str] = [
        _RUNTIME_PROTOCOL.strip(),
        "",
        "# 运行上下文",
        json.dumps(context, ensure_ascii=False, indent=2),
    ]
    general = [r for r in bundle.rule_ids if not rules[r].startswith(STAGE_RULES_PREFIX)]
    stage = [r for r in bundle.rule_ids if rules[r].startswith(STAGE_RULES_PREFIX)]
    for rule_id in [*general, *stage]:
        parts.extend(["", f"# 规则 {rule_id}", _read(project_root, rules[rule_id])])
    parts.extend(["", "# 本轮提交", SUBMISSION_NOTE])
    return "\n".join(parts).strip() + "\n"


def prompt_segments(
    bundle: TaskBundle,
    *,
    project_root: Path,
    rules: dict[str, str],
    run_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """The pieces of ``build_prompt`` with their origin (injection manifest).

    Each ``content`` is an exact substring of the built prompt; ``origin`` is
    ``builtin`` (code), ``runtime`` (per-session context), ``default`` or ``user``.
    """
    context = dict(run_context)
    if bundle.knowledge_sources:
        context["knowledge_sources"] = [item.to_dict() for item in bundle.knowledge_sources]
    segs: list[dict[str, Any]] = [
        {"id": "runtime_protocol", "kind": "builtin", "source": "src/backend/core/workflow/execution/prompt_build.py",
         "origin": "builtin", "content": _RUNTIME_PROTOCOL.strip()},
        {"id": "run_context", "kind": "runtime", "source": "orchestrator run context", "origin": "runtime",
         "content": "# 运行上下文\n" + json.dumps(context, ensure_ascii=False, indent=2)},
    ]
    general = [r for r in bundle.rule_ids if not rules[r].startswith(STAGE_RULES_PREFIX)]
    stage = [r for r in bundle.rule_ids if rules[r].startswith(STAGE_RULES_PREFIX)]
    for rule_id in [*general, *stage]:
        found = harness_fs.resolve(project_root, rules[rule_id])
        segs.append({
            "id": f"rule:{rule_id}", "kind": "rule", "source": rules[rule_id],
            "origin": found.source if found is not None else "missing",
            "file_sha256": found.sha256 if found is not None else None,
            "content": f"# 规则 {rule_id}\n" + _read(project_root, rules[rule_id]),
        })
    segs.append({"id": "submission_note", "kind": "builtin", "source": "src/backend/core/workflow/execution/prompt_build.py",
                 "origin": "builtin", "content": "# 本轮提交\n" + SUBMISSION_NOTE})
    return segs


def _read(project_root: Path, relative: str) -> str:
    found = harness_fs.resolve(project_root, relative)
    path = found.path if found is not None else project_root / relative
    return path.read_text(encoding="utf-8").strip()
