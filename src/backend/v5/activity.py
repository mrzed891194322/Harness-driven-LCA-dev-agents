"""#1 structured activity stream for the /runs page, built only from the run event log.

pi-runtime turns session activity into ``assistant_text`` / ``tool_call`` / ``tool_result`` events (pi_driver writes
them with node/rev/agent/attempt bound); the host adds orchestration events. ``items`` maps them to display items
with a stable ``seq`` so the GUI polls ``/api/workflow/progress?after_seq=N``. Nothing is read from session files.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

NOTE_TEXT = {
    "run_start": "开始运行 {workflow}",
    "model_preflight": "模型预检：{ok_text}",
    "node_start": "开始阶段 {label}",
    "node_end": "阶段 {label} 结束：{outcome}",
    "submit_rejected": "{label} / {agent} 提交被拒",
    "nudge": "{label} / {agent} 未提交，提醒第 {detail} 次",
    "model_retry": "{label} / {agent} 模型请求失败，重试：{detail}",
    "turn_aborted": "{label} / {agent} 回合中止：{detail}",
    "redo_requested": "{label} 请求回溯 {target}：{field}",
    "redo_approved": "{label} 回溯获批：{target}",
    "queue_append": "回溯到 {target}，插入重做：{segment}",
    "redo_refused": "{label} 回溯被拒：{reason}",
    "host_checks": "{label} 交付物检查未通过",
    "stop_requested": "收到中止请求",
    "requires_failed": "{label} 缺少输入",
    "run_end": "运行结束：{status}",
}
ACTIVITY = ("assistant_text", "tool_call", "tool_result")
CONTEXT = ("node", "rev", "agent", "attempt")


def node_label(node: str, redo: int) -> str:
    return f"{node}（重做 {redo}）" if redo else node


def _fmt(tpl: str, values: dict[str, Any]) -> str:
    vals = {k: "" for k in ("workflow", "label", "agent", "status", "outcome", "detail", "target", "field", "segment", "reason")}
    vals.update({k: (", ".join(map(str, v)) if isinstance(v, list) else str(v)) for k, v in values.items()})
    try:
        return tpl.format_map(vals)
    except (KeyError, ValueError):
        return tpl


def items(events: list[dict[str, Any]], ws: Path | None = None) -> list[dict[str, Any]]:
    strip = [str(ws.parent.resolve()) + "/", str(ws.parent) + "/"] if ws else []

    def clean(text: Any) -> str:
        out = str(text or "")
        for prefix in strip:
            out = out.replace(prefix, "")
        return out

    redo_of: dict[tuple[str, int], int] = {}  # (node, rev) -> redo count shown in titles
    redo_count: dict[str, int] = {}
    model: dict[tuple, str] = {}
    out: list[dict[str, Any]] = []
    for e in events:
        kind = e.get("kind", "")
        node, rev = str(e.get("node") or ""), int(e.get("rev") or 0)
        if kind == "node_start" and node and e.get("redo") and (node, rev) not in redo_of:
            redo_count[node] = redo_count.get(node, 0) + 1
            redo_of[(node, rev)] = redo_count[node]
        redo = redo_of.get((node, rev), 0)
        base = {"seq": int(e.get("seq") or 0), "ts": e.get("ts") or "",
                **{k: e[k] for k in CONTEXT if e.get(k) not in (None, "")}}
        if node:
            base["redo"] = redo
        turn = (node, rev, e.get("agent"), e.get("attempt"))
        if kind == "turn_start":
            model[turn] = str(e.get("model") or "")
            continue
        if kind in ACTIVITY or kind == "turn_end":
            base["model"] = model.get(turn, "")
        if kind == "assistant_text":
            if str(e.get("summary") or "").strip():
                out.append({**base, "kind": kind, "text": str(e["summary"]).strip()})
        elif kind in ("tool_call", "tool_result"):
            out.append({**base, "kind": kind, "tool": str(e.get("tool") or ""), "tool_call_id": e.get("tool_call_id"),
                        "summary": clean(e.get("summary")), "is_error": bool(e.get("is_error")),
                        "handoff": bool(e.get("handoff"))})
        elif kind == "turn_end":
            failed = bool(e.get("error")) and not e.get("submitted")
            out.append({**base, "kind": kind, "is_error": failed})
            if failed:
                out.append({**base, "kind": "error", "text": str(e.get("error"))[:500]})
        elif kind in NOTE_TEXT:
            segment = " → ".join(f"{i.get('node')}@rev{i.get('rev')}" for i in e.get("items") or [])
            text = _fmt(NOTE_TEXT[kind], {**e, "label": node_label(node, redo), "segment": segment,
                                          "ok_text": "通过" if e.get("ok") else f"失败 {e.get('error', '')}"})
            model_error = kind == "model_retry" or (kind == "turn_aborted" and "model_error" in str(e.get("detail", "")))
            out.append({**base, "kind": "note", "text": f"模型连接失败：{text}" if model_error else text,
                        "is_error": model_error})
    return out
