"""Session injection in the approved order.

System prompt: 1 global rules -> (2 permissions: host interception, not text) -> 3 role prompt
-> 4 tools and skills list.
User message: 5 <plan> (full) + <inputs> (paths + short notes) -> 6 <deliverable_X>
(spec description + schema summary) -> 7 <rework> (round 2+ only, "only change these").
Knowledge is not injected; a global rule explains where it is and when to read it.
"""
from __future__ import annotations

from pathlib import Path

from backend.v5 import layout
from backend.v5.config import Node, Spec, load_global_rules, load_role_def, load_rule

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


class Injector:
    def __init__(self, root: Path, workspace: Path | None = None) -> None:
        self.root = root
        self.ws = workspace or (root / layout.WORKSPACE)
        # Preview only: {plan file name: text} shown instead of / in addition to artifacts/plan (no writes).
        self.plan_override: dict[str, str] = {}

    # ---- system prompt (1, 3, 4) ----
    def system(self, node: Node, role: str) -> str:
        parts = []
        for rule in load_global_rules(self.root, role):
            parts.append(f"# {rule.title}\n{rule.prompt.strip()}")
        for extra in node.inject + node.agents[role].rules:
            rule = load_rule(self.root, extra)
            if rule.enabled and (rule.applies_to is None or role in rule.applies_to):
                parts.append(f"# {rule.title}\n{rule.prompt.strip()}")
        role_def = load_role_def(self.root, node.agents[role].role)
        parts.append(f"# {role_def.title}\n{role_def.prompt.strip()}" if role_def.title else role_def.prompt.strip())
        tools = node.agents[role].tools
        lines = ["# 工具与技能", "- 文件工具：read、ls、grep、find" + ("、write、edit" if role == "executor" else "") + "；完成时调用 submit。"]
        if tools.mcp:
            lines.append("- MCP：" + "、".join(tools.mcp))
        for skill in tools.skills:
            lines.append(f"- 技能 {skill}：`harness/tools/skills/{skill}/SKILL.md`（需要时自己读取）")
        parts.append("\n".join(lines))
        return "\n\n".join(parts) + "\n"

    # ---- user message (5, 6, 7) ----
    def __call__(self, node: Node, role: str, rnd: int, rework: str | None, specs: dict[str, Spec]) -> str:
        art = self.ws / "artifacts"
        out = []
        plan_dir = art / "plan"
        plans = sorted(plan_dir.glob("*.md")) if plan_dir.is_dir() else []
        texts = {p.name: p.read_text(encoding="utf-8") for p in plans}
        texts.update(self.plan_override)
        out.append(_section("plan", "\n\n".join(texts[k] for k in sorted(texts)) or "（无计划）"))
        inputs = []
        for req in node.requires:
            target = art / req
            kind = "目录" if target.is_dir() else "文件"
            count = f"，{sum(1 for p in target.rglob('*') if p.is_file())} 个文件" if target.is_dir() else ""
            note = "，最新版本" if node.revision and ".rev" in req else ""
            inputs.append(f"- `{target}`（{kind}{count}{note}，上游产物，只读）")
        out.append(_section("inputs", "\n".join(inputs) or "（本节点没有上游产物）"))
        runs = layout.node_dir(self.ws, node.id)
        for prod in node.produces:
            spec = specs[prod.spec]
            body = [f"交付路径：`{art / prod.path}`", spec.prompt.strip()]
            if node.revision:
                n = node.revision
                body.insert(1, f"本次是第 {n} 版修订：原文件和更早版本保持不动（只读）。本节点在产出目录写的每个文件/目录都在扩展名前加 "
                               f"`.rev{n}`（如 `bom.rev{n}.md`、`LCI.rev{n}/`、`results.rev{n}.json`、`raw.rev{n}/`），"
                               f"规格里写的无后缀文件名都按此改名；文件内互相引用的路径也用改名后的。")
            summary = schema_summary(spec.schema_)
            if summary:
                body.append(f"结构摘要（完整 schema：`harness/specs/{spec.id}.yaml` 的 schema）：\n{summary}")
            if role == "reviewer":
                body.insert(0, "审核对象：")
            out.append(_section(f"deliverable_{spec.id}", "\n\n".join(body)))
        if role == "reviewer":
            out.append(f"审核笔记可写到 `{runs / 'reviewer'}`。")
        else:
            out.append(f"中间文件写到 `{runs}`。")
        if rework and rnd > 1:
            out.append(_section("rework", "只改下面这些问题，其他保持不变。\n\n" + rework))
        return "\n\n".join(out) + "\n"
