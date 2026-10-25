"""#1 structured activity stream for the /runs page, built only from the run event log.

pi-runtime turns session activity into ``assistant_text`` / ``tool_call`` / ``tool_result`` events (pi_driver writes
them with node/rev/agent/attempt bound); the host adds orchestration events. ``items`` maps them to display items
with a stable ``seq`` so the GUI polls ``/api/workflow/progress?after_seq=N``. Nothing is read from session files.

I-58: ``ActivityCache`` keeps already-parsed events/items and the redo-title globals; each poll only reads bytes
appended since the last size and extends the cache.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.workflow.events import EventLog

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
    "host_checks": "{label} 交付物检查：{ok_text}",
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


def _extend(events: list[dict[str, Any]], *, redo_of: dict, redo_count: dict, model: dict,
            out: list[dict[str, Any]], ws: Path | None) -> None:
    """Append display items for ``events``; mutates redo/model globals and ``out`` in place (I-58)."""
    strip = [str(ws.parent.resolve()) + "/", str(ws.parent) + "/"] if ws else []

    def clean(text: Any) -> str:
        s = str(text or "")
        for prefix in strip:
            s = s.replace(prefix, "")
        return s

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
            if kind == "host_checks":
                ok_text = "通过" if e.get("ok") else "未通过"
            else:
                ok_text = "通过" if e.get("ok") else f"失败 {e.get('error', '')}"
            text = _fmt(NOTE_TEXT[kind], {**e, "label": node_label(node, redo), "segment": segment,
                                          "ok_text": ok_text})
            model_error = kind == "model_retry" or (kind == "turn_aborted" and "model_error" in str(e.get("detail", "")))
            host_fail = kind == "host_checks" and not e.get("ok")
            out.append({**base, "kind": "note", "text": f"模型连接失败：{text}" if model_error else text,
                        "is_error": model_error or host_fail})


def items(events: list[dict[str, Any]], ws: Path | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    _extend(events, redo_of={}, redo_count={}, model={}, out=out, ws=ws)
    return out


@dataclass
class ActivityCache:
    """Parsed events.jsonl + activity items + redo-title globals for one workspace (I-58)."""

    path: Path
    ws: Path
    inode: int = 0
    size: int = 0
    mtime_ns: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    items: list[dict[str, Any]] = field(default_factory=list)
    redo_of: dict = field(default_factory=dict)
    redo_count: dict = field(default_factory=dict)
    model: dict = field(default_factory=dict)

    def refresh(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        path = self.path
        if not path.is_file():
            self.inode = self.size = self.mtime_ns = 0
            self.events.clear(); self.items.clear()
            self.redo_of.clear(); self.redo_count.clear(); self.model.clear()
            return self.events, self.items
        st = path.stat()
        if st.st_ino == self.inode and st.st_size == self.size and st.st_mtime_ns == self.mtime_ns:
            return self.events, self.items
        # Truncated, replaced, or same-size rewrite → rebuild. Pure append → extend.
        if st.st_ino != self.inode or st.st_size < self.size or (
            st.st_size == self.size and st.st_mtime_ns != self.mtime_ns
        ):
            self.size = 0
            self.events.clear(); self.items.clear()
            self.redo_of.clear(); self.redo_count.clear(); self.model.clear()
        new_events = EventLog.read_bytes(path, self.size, st.st_size)
        if new_events:
            self.events.extend(new_events)
            _extend(new_events, redo_of=self.redo_of, redo_count=self.redo_count, model=self.model,
                    out=self.items, ws=self.ws)
        self.inode, self.size, self.mtime_ns = st.st_ino, st.st_size, st.st_mtime_ns
        return self.events, self.items


_CACHES: dict[str, ActivityCache] = {}


def cached_progress(ws: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (events, items) for ``ws``, reading only newly appended event bytes when possible."""
    key = str(ws.resolve())
    cache = _CACHES.get(key)
    path = ws / "runs" / "_run" / "events.jsonl"
    if cache is None or cache.path != path:
        cache = ActivityCache(path=path, ws=ws)
        _CACHES[key] = cache
    return cache.refresh()
