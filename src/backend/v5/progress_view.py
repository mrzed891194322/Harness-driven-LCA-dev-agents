"""Read-only feed for the restored 599ed0a /runs page (实时终端 + 活动概览).

Builds the old progress text format (`[stage(agent#attempt)-worker-HH:MM:SS] body`, `[orchestrator-HH:MM:SS] ...`)
and the old activity events from v5 data: the run event log plus each agent's live pi session file
(`workspace/tmp/pi-v5/<node>.<agent>/session.jsonl`). Nothing is written.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ORCH_TEXT = {
    "run_start": "开始运行 {workflow}",
    "model_preflight": "模型预检：{ok_text}",
    "node_start": "开始阶段 {node}",
    "node_end": "阶段 {node} 结束：{status}",
    "review_verdict": "{node} 审核结论：{verdict}",
    "submit_rejected": "{node} / {agent} 提交被拒",
    "nudge": "{node} / {agent} 未提交，提醒第 {detail} 次",
    "model_retry": "{node} / {agent} 模型请求失败，重试：{detail}",
    "turn_aborted": "{node} / {agent} 回合中止：{detail}",
    "stop_requested": "收到中止请求",
    "requires_failed": "{node} 缺少输入",
    "run_end": "运行结束：{status}",
}
# Errors the old AgentStream shows as model-connection failures (turnFailureKind).
_CACHE: dict[str, tuple[float, int, list[dict]]] = {}


def _ts(value: Any) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _clock(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%H:%M:%S") if t else "00:00:00"


def _session_rows(path: Path) -> list[dict]:
    try:
        st = path.stat()
    except OSError:
        return []
    key = str(path)
    hit = _CACHE.get(key)
    if hit and hit[0] == st.st_mtime and hit[1] == st.st_size:
        return hit[2]
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(e, dict) and e.get("type") == "message" and isinstance(e.get("message"), dict):
            rows.append(e)
    _CACHE[key] = (st.st_mtime, st.st_size, rows)
    return rows


def _detail(args: Any) -> str:
    if not isinstance(args, dict):
        return ""
    for k in ("path", "pattern", "command", "query", "name"):
        if args.get(k):
            return str(args[k])[:160]
    return json.dumps(args, ensure_ascii=False)[:160]


def _first_line(content: Any) -> str:
    if isinstance(content, list):
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text" and c.get("text"):
                return str(c["text"]).strip().splitlines()[0][:200] if str(c["text"]).strip() else ""
    return ""


def build(ws: Path, events: list[dict], model: str = "") -> tuple[str, list[dict]]:
    """(progress text, activity events) for the current run."""
    items: list[tuple[float, int, str, dict | None]] = []  # (time, order, text block, activity event)
    turns: dict[str, list[tuple[float, int]]] = {}  # node.agent -> [(start ts, round)]
    order = 0
    for e in events:
        t = _ts(e.get("ts"))
        kind = e.get("kind", "")
        if kind == "turn_start" and e.get("node") and e.get("agent"):
            turns.setdefault(f"{e['node']}.{e['agent']}", []).append((t, int(e.get("attempt") or 0)))
        if kind == "agent_settled" and e.get("node") and e.get("agent"):
            items.append((t, order, "", {"node": e["node"], "agent": e["agent"], "attempt": int(e.get("attempt") or 0),
                                         "kind": "turn_end", "is_error": bool(e.get("error")) and not e.get("submitted"),
                                         "ts": e.get("ts")}))
        tpl = ORCH_TEXT.get(kind)
        if tpl:
            vals = {k: str(v) for k, v in e.items()}
            vals.setdefault("detail", "")
            vals["ok_text"] = "通过" if e.get("ok") else f"失败 {e.get('error', '')}"
            try:
                text = tpl.format_map({**{k: "" for k in ("workflow", "node", "agent", "status", "verdict")}, **vals})
            except (KeyError, ValueError):
                text = kind
            if kind == "model_retry" or (kind == "turn_aborted" and "model_error" in str(e.get("detail", ""))):
                text = f"模型连接失败：{text}"
            items.append((t, order, f"[orchestrator-{_clock(t)}] {text}", None))
        order += 1
    for key, starts in turns.items():
        node, agent = key.rsplit(".", 1)
        starts.sort()
        first = starts[0][0]
        worker = (model or "pi").split("/")[-1]
        for row in _session_rows(ws / "tmp" / "pi-v5" / key / "session.jsonl"):
            t = _ts(row.get("timestamp"))
            if t + 1 < first:
                continue  # an earlier run's session
            rnd = max((r for s, r in starts if s <= t + 1), default=starts[0][1])
            m = row["message"]
            if m.get("model"):
                worker = str(m["model"])
            tag = f"[{node}({agent}#{rnd})-{worker.replace('-', '_')}-{_clock(t)}]"
            base = {"node": node, "agent": agent, "attempt": rnd, "ts": row.get("timestamp")}
            if m.get("role") == "assistant":
                for c in m.get("content") or []:
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "text" and str(c.get("text") or "").strip():
                        items.append((t, order, f"{tag}\n{c['text'].strip()}", None))
                    elif c.get("type") == "toolCall":
                        name = str(c.get("name") or "")
                        d = _detail(c.get("arguments")).replace(str(ws.parent.resolve()) + "/", "").replace(str(ws.parent) + "/", "")
                        items.append((t, order, f"{tag} → {name} {d}".rstrip(), {**base, "kind": "tool_call", "tool": name,
                                      "tool_call_id": c.get("id"), "summary": d, "handoff": name.endswith("submit")}))
                    order += 1
                if m.get("stopReason") == "error":
                    items.append((t, order, f"{tag} error: {m.get('errorMessage') or 'provider error'}", None))
            elif m.get("role") == "toolResult":
                name = str(m.get("toolName") or "")
                err = bool(m.get("isError"))
                msg = _first_line(m.get("content")) if err else ""
                items.append((t, order, f"{tag} {'✗' if err else '✓'} {name}{(': ' + msg) if msg else ''}",
                              {**base, "kind": "tool_result", "tool": name, "tool_call_id": m.get("toolCallId"),
                               "is_error": err, "summary": msg, "handoff": name.endswith("submit")}))
            order += 1
    items.sort(key=lambda x: (x[0], x[1]))
    text = "\n".join(i[2] for i in items if i[2])
    activity = [i[3] for i in items if i[3]]
    return (text + "\n" if text else ""), activity
