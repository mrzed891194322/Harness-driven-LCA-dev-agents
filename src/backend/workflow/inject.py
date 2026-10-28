"""Session injection in the approved order.

System prompt: 1 global rules -> (2 permissions: host interception, not text) -> 3 agent prompt
-> 4 tools and skills list.
User message: 5 <plan> (full) + <inputs> (paths + short notes) -> 6 <deliverable_X>
(spec description + schema summary) -> 7 <rework> (round 2+ only, "only change these").
Knowledge is not injected; a global rule explains where it is and when to read it.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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



def _skill_prompt_path(skill: str) -> tuple[str, str]:
    """Resolve a ``tools.skills`` entry to (repo-rel SKILL.md path, display name).

    Short names map to ``harness/tools/skills/<name>/SKILL.md``. Entries with ``/``
    or starting with ``.`` are treated as repo-root-relative paths: a ``SKILL.md``
    file, or a directory that contains one.
    """
    raw = (skill or "").strip()
    if not raw:
        return "harness/tools/skills/?/SKILL.md", "?"
    if "/" in raw or raw.startswith("."):
        rel = Path(raw)
        if rel.name != "SKILL.md":
            rel = rel / "SKILL.md"
        return rel.as_posix(), rel.parent.name
    return f"harness/tools/skills/{raw}/SKILL.md", raw


class Injector:
    def __init__(self, root: Path, workspace: Path | None = None) -> None:
        self.root = root
        self.ws = workspace or (root / layout.WORKSPACE)
        # Preview only: {plan file name: text} shown instead of / in addition to artifacts/plan (no writes).
        self.plan_override: dict[str, str] = {}

    def describe_injection(self, node: Node, agent: str) -> dict:
        """Backward-compatible planned/actual rule snapshot (work-record)."""
        report = self.build_session_injection_report(node, agent, attempt=0, user_prompt="")
        return {
            "planned": report.get("planned") or {},
            "actual": report.get("actual") or {},
            "sections": report.get("sections") or {},
            "ok": report.get("ok"),
        }

    def build_session_injection_report(
        self,
        node: Node,
        agent: str,
        *,
        attempt: int,
        user_prompt: str,
        run_id: str = "",
        rev: int | None = None,
    ) -> dict[str, Any]:
        """Today's口径: three sections (system / tools / user) with ok/fail each.

        Not the 10-10 intended↔effective diff. Host-authored; pi first_request.json is对照 only.
        """
        role = node.role(agent)
        planned_global: list[str] = []
        loaded: list[str] = []
        rule_failed: list[dict[str, str]] = []
        rule_paths: list[str] = []

        try:
            for rule in load_global_rules(self.root, role):
                planned_global.append(rule.id)
                loaded.append(rule.id)
                rule_paths.append(rule.id)
        except Exception as exc:  # noqa: BLE001
            rule_failed.append({"path": "rules/global/*", "error": str(exc)[:300]})

        planned_inject = list(node.inject)
        planned_agent = list(node.agents[agent].rules)
        skipped_rules: list[dict[str, str]] = []
        for rel in planned_inject + planned_agent:
            try:
                rule = load_rule(self.root, rel)
                if rule.enabled and (rule.applies_to is None or role in rule.applies_to):
                    loaded.append(rule.id or rel)
                    rule_paths.append(rel)
                else:
                    skipped_rules.append({"path": rel, "error": "disabled_or_not_applicable"})
            except Exception as exc:  # noqa: BLE001
                rule_failed.append({"path": rel, "error": str(exc)[:300]})

        system_text = ""
        system_errors: list[dict[str, str]] = list(rule_failed)
        try:
            system_text = self.system(node, agent)
        except Exception as exc:  # noqa: BLE001
            system_errors.append({"path": "(system)", "error": str(exc)[:300]})
        system_ok = bool(system_text.strip()) and not system_errors

        tools = node.agents[agent].tools
        file_tools = (
            ["read", "ls", "grep", "find", "write", "edit"]
            if role == "executor"
            else ["read", "ls", "grep", "find", "write"]
        )
        skill_rows: list[dict[str, Any]] = []
        tool_errors: list[dict[str, str]] = []
        for skill in tools.skills:
            rel, label = _skill_prompt_path(skill)
            path = self.root / rel
            exists = path.is_file()
            skill_rows.append({"name": label, "path": rel, "ok": exists})
            if not exists:
                tool_errors.append({"path": rel, "error": "skill_missing"})
        tools_ok = not tool_errors

        user_text = user_prompt or ""
        user_errors: list[dict[str, str]] = []
        segments: list[str] = []
        for name in ("plan", "inputs", "rework", "redo_policy", "redo_reason", "executor_submit"):
            if f"<{name}>" in user_text:
                segments.append(name)
        segments += [f"deliverable_{m}" for m in re.findall(r"<deliverable_([^>]+)>", user_text)]
        if not user_text.strip():
            user_errors.append({"path": "(user_prompt)", "error": "empty_user_prompt"})
        user_ok = bool(user_text.strip()) and not user_errors

        overall = system_ok and tools_ok and user_ok
        sections = {
            "system_prompt": {
                "ok": system_ok,
                "label": "顶层提示词",
                "paths": rule_paths,
                "skipped": skipped_rules,
                "agent_title": (node.agents[agent].definition.title or ""),
                "chars": len(system_text),
                "content": system_text,
                "errors": system_errors,
            },
            "tools": {
                "ok": tools_ok,
                "label": "工具",
                "file_tools": file_tools + ["submit"],
                "mcp": list(tools.mcp),
                "skills": skill_rows,
                "errors": tool_errors,
            },
            "user_prompt": {
                "ok": user_ok,
                "label": "普通提示词",
                "segments": segments,
                "chars": len(user_text),
                "content": user_text,
                "errors": user_errors,
            },
        }
        return {
            "schema": "harness.injection.session/2",
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "run_id": run_id,
            "node": node.id,
            "run_key": node.run_key,
            "rev": node.rev if rev is None else rev,
            "agent": agent,
            "attempt": attempt,
            "role": role,
            "planned": {
                "global_rules": planned_global,
                "inject": planned_inject,
                "agent_rules": planned_agent,
            },
            "actual": {
                "loaded": loaded,
                "failed": rule_failed,
                "system_chars": len(system_text),
                "ok": overall,
            },
            "sections": sections,
            "ok": overall,
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
            rel, label = _skill_prompt_path(skill)
            lines.append(f"- 技能 {label}：`{rel}`（需要时自己读取）")
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
            notes = runs / agent / "notes.md"
            out.append(f"审核笔记可写到 `{notes}`（必须是该文件路径；`{runs / agent}` 是节点目录，禁止用 write 覆盖成文件）。")
        else:
            out.append(f"中间文件写到 `{runs}`。")
        if rework and attempt > 1:
            out.append(_section("rework", "只改下面这些问题，其他保持不变。\n\n" + rework))
        return "\n\n".join(out) + "\n"


SESSION_INJECTION_SCHEMA = "harness.injection.session/2"


def session_snapshot_dir(
    root: Path, run_id: str, node_id: str, agent: str, attempt: int, *, rev: int = 0
) -> Path:
    """Match pi-runtime sessionSnapshotDir: .local/runs/<run>/sessions/<node>[@rev].<agent>.<attempt>/"""

    def safe(s: str) -> str:
        return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in (s or "x"))

    node_part = f"{node_id}@rev{rev}" if rev else node_id
    return (
        root
        / ".local"
        / "runs"
        / safe(run_id or "adhoc")
        / "sessions"
        / f"{safe(node_part)}.{safe(agent)}.{int(attempt) or 0}"
    )


def render_session_injection_md(report: dict[str, Any]) -> str:
    """Human-readable per-session injection doc (today's three-section口径)."""
    sections = report.get("sections") or {}
    lines = [
        "# 会话注入文档 / Session injection",
        "",
        f"- schema: `{report.get('schema')}`",
        f"- run_id: `{report.get('run_id') or '—'}`",
        f"- node: `{report.get('node')}` run_key=`{report.get('run_key')}` rev={report.get('rev')}",
        f"- agent: `{report.get('agent')}` role=`{report.get('role')}` attempt={report.get('attempt')}",
        f"- overall: **{'OK' if report.get('ok') else 'FAIL'}**",
        "",
        "> 对齐 docs/architecture/DESIGN.md：顶层规则 → 工具技能 → 任务上下文用户消息。",
        "> 非 10-10 intended↔effective；pi-runtime `injection/first_request.json` 仅作对照。",
        "",
    ]
    for key in ("system_prompt", "tools", "user_prompt"):
        sec = sections.get(key) or {}
        mark = "成功" if sec.get("ok") else "失败"
        lines.append(f"## {sec.get('label') or key}（注入{mark}）")
        lines.append("")
        if key == "system_prompt":
            paths = sec.get("paths") or []
            lines.append(f"- 路径/规则：{', '.join(f'`{p}`' for p in paths) or '（无）'}")
            if sec.get("agent_title"):
                lines.append(f"- agent prompt：{sec['agent_title']}")
            lines.append(f"- 字符数：{sec.get('chars', 0)}")
            for err in sec.get("errors") or []:
                lines.append(f"- ERROR `{err.get('path')}`: {err.get('error')}")
            lines.append("")
            lines.append("### 内容")
            lines.append("")
            lines.append("```text")
            lines.append((sec.get("content") or "").rstrip() or "（空）")
            lines.append("```")
        elif key == "tools":
            lines.append(f"- 文件工具：{', '.join(sec.get('file_tools') or []) or '（无）'}")
            lines.append(f"- MCP：{', '.join(sec.get('mcp') or []) or '（无）'}")
            skills = sec.get("skills") or []
            if not skills:
                lines.append("- 技能：（无）")
            else:
                for sk in skills:
                    st = "OK" if sk.get("ok") else "MISSING"
                    lines.append(f"- 技能 [{st}] `{sk.get('name')}` → `{sk.get('path')}`")
            for err in sec.get("errors") or []:
                lines.append(f"- ERROR `{err.get('path')}`: {err.get('error')}")
        else:
            segs = sec.get("segments") or []
            lines.append(f"- 分段：{', '.join(segs) or '（未解析到标签）'}")
            lines.append(f"- 字符数：{sec.get('chars', 0)}")
            for err in sec.get("errors") or []:
                lines.append(f"- ERROR `{err.get('path')}`: {err.get('error')}")
            lines.append("")
            lines.append("### 内容")
            lines.append("")
            lines.append("```text")
            lines.append((sec.get("content") or "").rstrip() or "（空）")
            lines.append("```")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_session_injection_doc(root: Path, report: dict[str, Any]) -> Path:
    """Write injection.md + injection.json under the session snapshot dir."""
    dest = session_snapshot_dir(
        root,
        str(report.get("run_id") or "adhoc"),
        str(report.get("node") or "node"),
        str(report.get("agent") or "agent"),
        int(report.get("attempt") or 0),
        rev=int(report.get("rev") or 0),
    )
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "injection.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (dest / "injection.md").write_text(render_session_injection_md(report), encoding="utf-8")
    return dest


def injection_event_payload(report: dict[str, Any], *, session_doc: str = "") -> dict[str, Any]:
    """Compact structured fields for events.jsonl ``injection``."""
    sections = report.get("sections") or {}
    compact: dict[str, Any] = {}
    for key, sec in sections.items():
        if not isinstance(sec, dict):
            continue
        row: dict[str, Any] = {
            "ok": sec.get("ok"),
            "label": sec.get("label"),
            "errors": sec.get("errors") or [],
        }
        if key == "system_prompt":
            row.update({"paths": sec.get("paths") or [], "chars": sec.get("chars", 0)})
        elif key == "tools":
            row.update(
                {
                    "file_tools": sec.get("file_tools") or [],
                    "mcp": sec.get("mcp") or [],
                    "skills": sec.get("skills") or [],
                }
            )
        else:
            row.update({"segments": sec.get("segments") or [], "chars": sec.get("chars", 0)})
        compact[key] = row
    return {
        "schema": report.get("schema"),
        "ok": report.get("ok"),
        "planned": report.get("planned") or {},
        "actual": report.get("actual") or {},
        "sections": compact,
        "session_doc": session_doc,
    }
