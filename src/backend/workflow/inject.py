"""Session injection in the approved order.

System prompt: 1 global rules -> (2 permissions: host interception, not text) -> 3 agent prompt
-> 4 tools and skills list.
User message: 5 <plan> (full) + <inputs> (paths + short notes) -> 6 <deliverable_X>
(spec description + schema summary) -> 7 <rework> (round 2+ only, "only change these").
Knowledge is not injected; a global rule explains where it is and when to read it.
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.workflow import layout
from backend.workflow.config import Node, Spec, load_global_rules, load_rule, resolve_spec_path

MAX_SCHEMA_SUMMARY = 4000


def _section(name: str, body: str) -> str:
    return f"<{name}>\n{body.strip()}\n</{name}>"


def schema_summary(schema: dict | None) -> str:
    if not schema:
        return ""

    def walk(node: dict, path: str, out: list[str], depth: int) -> None:
        if depth > 6 or not isinstance(node, dict):
            return
        typ = node.get("type", "")
        req = set(node.get("required") or [])
        desc = node.get("description", "")
        out.append(f"- {path or '(根)'}: {typ}{'；' + desc if desc else ''}")
        for key, child in (node.get("properties") or {}).items():
            mark = "（必填）" if key in req else ""
            walk(child, f"{path}.{key}{mark}" if path else f"{key}{mark}", out, depth + 1)
        if isinstance(node.get("items"), dict):
            walk(node["items"], f"{path}[]", out, depth + 1)

    lines: list[str] = []
    walk(schema, "", lines, 0)
    text = "\n".join(lines)
    return text[:MAX_SCHEMA_SUMMARY]


REDO_RULE_EXECUTOR = ("凡是你自己能在本节点修正的问题，不得报告 blocked，也不得请求回溯上游；"
                      "只有满足上面判据时才用 redo_upstream，并给出证据。")
REDO_RULE_REVIEWER = "不满足判据的回溯请求一律 reject；符合判据才用 approve_redo_upstream。"


def redo_policy(node: Node, specs: dict[str, Spec], targets: dict[str, list[str]], role: str) -> str:
    """<redo_policy> from the produced specs' ``upstream`` sections (WORKFLOW_DESIGN §4)."""
    criteria, not_up = [], []
    for prod in node.produces:
        spec = specs.get(prod.spec)
        if spec is None:
            continue
        criteria += [c for c in spec.upstream.criteria if c not in criteria]
        not_up += [c for c in spec.upstream.not_upstream if c not in not_up]
    if not targets:
        return "本节点不能请求回溯上游（没有可回溯的上游节点）。" + ("问题都在本节点内解决。" if role == "executor" else "")
    lines = ["可回溯的上游节点及其交付物：" + "；".join(f"{n}（{', '.join(p)}）" for n, p in targets.items())]
    if criteria:
        lines.append("允许回溯的判据：\n" + "\n".join(f"- {c}" for c in criteria))
    else:
        lines.append("允许回溯的判据：上游交付物有错误或缺失，且本节点无法从资料自行确定。")
    if not_up:
        lines.append("不属于回溯的情况（本节点自行处理）：\n" + "\n".join(f"- {c}" for c in not_up))
    lines.append(REDO_RULE_EXECUTOR if role == "executor" else REDO_RULE_REVIEWER)
    return "\n\n".join(lines)


def redo_reason_text(redo: dict) -> str:
    return (f"本节点因下游 {redo.get('requested_by')} 的回溯请求而重做（已获审核批准）。\n"
            f"- 交付物：{redo.get('artifact')}；字段：{redo.get('field')}\n- 证据：{redo.get('evidence')}\n"
            f"- 要求的修改：{redo.get('requested_change')}\n上一版产物保留在原位置（只读），本次写新版本。")


class Injector:
    def __init__(self, root: Path, workspace: Path | None = None) -> None:
        self.root = root
        self.ws = workspace or (root / layout.WORKSPACE)
        # Preview only: {plan file name: text} shown instead of / in addition to artifacts/plan (no writes).
        self.plan_override: dict[str, str] = {}


    def describe_injection(self, node: Node, agent: str) -> dict:
        """Planned rule paths vs what actually loaded (for work-record / events)."""
        role = node.role(agent)
        planned_global = []
        loaded: list[str] = []
        failed: list[dict] = []
        try:
            for rule in load_global_rules(self.root, role):
                planned_global.append(rule.id)
                loaded.append(rule.id)
        except Exception as exc:  # noqa: BLE001
            failed.append({"path": "rules/global/*", "error": str(exc)[:300]})
        planned_inject = list(node.inject)
        planned_agent = list(node.agents[agent].rules)
        for rel in planned_inject + planned_agent:
            try:
                rule = load_rule(self.root, rel)
                if rule.enabled and (rule.applies_to is None or role in rule.applies_to):
                    loaded.append(rule.id or rel)
                else:
                    failed.append({"path": rel, "error": "disabled_or_not_applicable"})
            except Exception as exc:  # noqa: BLE001
                failed.append({"path": rel, "error": str(exc)[:300]})
        try:
            system = self.system(node, agent)
            system_chars = len(system)
            ok = not failed
        except Exception as exc:  # noqa: BLE001
            system_chars = 0
            ok = False
            failed.append({"path": "(system)", "error": str(exc)[:300]})
        return {
            "planned": {
                "global_rules": planned_global,
                "inject": planned_inject,
                "agent_rules": planned_agent,
            },
            "actual": {
                "loaded": loaded,
                "failed": failed,
                "system_chars": system_chars,
                "ok": ok,
            },
        }

    # ---- system prompt (1, 3, 4) ----
    def system(self, node: Node, agent: str) -> str:
        parts = []
        role = node.role(agent)
        for rule in load_global_rules(self.root, role):
            parts.append(f"# {rule.title}\n{rule.prompt.strip()}")
        for extra in node.inject + node.agents[agent].rules:
            rule = load_rule(self.root, extra)
            if rule.enabled and (rule.applies_to is None or role in rule.applies_to):
                parts.append(f"# {rule.title}\n{rule.prompt.strip()}")
        agent_def = node.agents[agent].definition
        parts.append(f"# {agent_def.title}\n{agent_def.prompt.strip()}" if agent_def.title else agent_def.prompt.strip())
        tools = node.agents[agent].tools
        lines = ["# 工具与技能", "- 文件工具：read、ls、grep、find" + ("、write、edit" if role == "executor" else "") + "；完成时调用 submit。"]
        if tools.mcp:
            lines.append("- MCP：" + "、".join(tools.mcp))
        for skill in tools.skills:
            lines.append(f"- 技能 {skill}：`harness/tools/skills/{skill}/SKILL.md`（需要时自己读取）")
        parts.append("\n".join(lines))
        return "\n\n".join(parts) + "\n"

    # ---- user message (5, 6, 7) ----
    def __call__(self, node: Node, agent: str, attempt: int, rework: str | None, specs: dict[str, Spec],
                 context: dict | None = None) -> str:
        ctx = context or {}
        role = node.role(agent)
        art = self.ws / "artifacts"
        out = []
        plan_dir = art / "plan"
        plans: list[Path] = []
        if plan_dir.is_dir():
            seen: set[str] = set()
            for pattern in ("*.yaml", "*.yml", "*.md"):
                for path in plan_dir.glob(pattern):
                    if path.name in seen:
                        continue
                    seen.add(path.name)
                    plans.append(path)
            plans.sort(key=lambda path: path.name)
        texts = {p.name: p.read_text(encoding="utf-8") for p in plans}
        texts.update(self.plan_override)
        out.append(_section("plan", "\n\n".join(texts[k] for k in sorted(texts)) or "（无计划）"))
        inputs = []
        for req in node.requires:
            target = art / req
            kind = "目录" if target.is_dir() else "文件"
            count = f"，{sum(1 for p in target.rglob('*') if p.is_file())} 个文件" if target.is_dir() else ""
            note = "，最新版本" if ".rev" in req else ""
            inputs.append(f"- `{target}`（{kind}{count}{note}，上游产物，只读）")
        out.append(_section("inputs", "\n".join(inputs) or "（本节点没有上游产物）"))
        runs = layout.node_dir(self.ws, node.run_key)
        for prod in node.produces:
            spec = specs[prod.spec]
            body = [f"交付路径：`{art / prod.path}`", spec.prompt.strip()]
            if node.rev:
                n = node.rev
                body.insert(1, f"本次是第 {n} 版（rev {n}）：原文件和更早版本保持不动（只读）。本节点在产出目录写的每个文件/目录都在扩展名前加 "
                               f"`.rev{n}`（如 `bom.rev{n}.md`、`LCI.rev{n}/`、`results.rev{n}.json`、`raw.rev{n}/`），"
                               f"规格里写的无后缀文件名都按此改名；文件内互相引用的路径也用改名后的。")
            summary = schema_summary(spec.schema_)
            if summary:
                # Spec.id is the file stem; resolve via produce path / Spec.path (repo-root-relative).
                spec_rel = spec.path or resolve_spec_path(self.root, prod.spec).relative_to(self.root).as_posix()
                body.append(f"结构摘要（完整 schema：`{spec_rel}` 的 schema）：\n{summary}")
            if role == "reviewer":
                body.insert(0, "审核对象：")
            out.append(_section(f"deliverable_{spec.id}", "\n\n".join(body)))
        policy = redo_policy(node, specs, ctx.get("redo_targets") or {}, role)
        if policy:
            out.append(_section("redo_policy", policy))
        if ctx.get("redo"):
            out.append(_section("redo_reason", redo_reason_text(ctx["redo"])))
        last = ctx.get("executor_last")
        if role == "reviewer":
            if last:
                out.append(_section("executor_submit", json.dumps(last, ensure_ascii=False, indent=2)))
            out.append(f"审核笔记可写到 `{runs / agent}`。")
        else:
            out.append(f"中间文件写到 `{runs}`。")
        if rework and attempt > 1:
            out.append(_section("rework", "只改下面这些问题，其他保持不变。\n\n" + rework))
        return "\n\n".join(out) + "\n"
