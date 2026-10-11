"""Render one session snapshot directory as readable Markdown (for humans / other agents)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_FIELD = 20_000


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _clip(text: Any, limit: int = MAX_FIELD) -> str:
    text = str(text or "")
    return text if len(text) <= limit else text[:limit] + f"\n…（截断，共 {len(text)} 字符；完整内容见 transcript.jsonl）"


def _fence(text: str, lang: str = "") -> str:
    fence = "````" if "```" in text else "```"
    return f"{fence}{lang}\n{text}\n{fence}"


def load_records(d: Path) -> list[dict[str, Any]]:
    """transcript.jsonl records with blob stubs expanded."""
    path = d / "transcript.jsonl"
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("blob"):
            full = _load(d / rec["blob"])
            if isinstance(full, dict):
                rec = {**full, "_blob": rec["blob"]}
        out.append(rec)
    return out


def render_session_markdown(d: Path, *, full: bool = False) -> str:
    clip = (lambda t: str(t or "")) if full else _clip
    intended = _load(d / "injection" / "intended.json") or {}
    effective = _load(d / "injection" / "effective.json") or {}
    diff = _load(d / "injection" / "diff.json") or {}
    first = _load(d / "injection" / "first_request.json")
    out: list[str] = [f"# 会话 {d.name}", ""]
    out += [f"- 运行：`{d.parent.parent.name}`", f"- 会话键：`{intended.get('session_key', '?')}`"]
    m = intended.get("model") or {}
    em = effective.get("model") or {}
    out.append(f"- 计划模型：`{m.get('provider')}/{m.get('model_id')}`；实际：`{em.get('provider')}/{em.get('model_id')}`")
    out.append(f"- 注入检查：**{diff.get('level', '未记录')}**")
    for i in diff.get("items", []):
        if i.get("level") != "ok":
            out.append(f"  - [{i['level']}] {i['item']}：{i['kind']}{'（关键）' if i.get('critical') else ''}")
    if first is not None:
        out.append(f"- 首个模型请求：已记录（含 system prompt：{first.get('system_prompt_found')}，工具 {len(first.get('tool_names') or [])} 个）")
    else:
        out.append("- 首个模型请求：未记录（会话未调用模型，或 runtime 未挂钩）")
    out += ["", "## 注入", "", "### 工具（实际暴露给模型）", ""]
    out += [f"- `{n}`" for n in effective.get("active_tool_names") or []] or ["- （未采集）"]
    out += ["", "### 权限", "", _fence(json.dumps(intended.get("permissions") or {}, ensure_ascii=False, indent=2), "json")]
    out += ["", "### 提示词段落", ""]
    for s in intended.get("segments") or []:
        out.append(f"- `{s.get('id')}` · {s.get('source', '')} · {s.get('origin', '')} · sha256={str(s.get('content_sha256', ''))[:12]}")
    recs = load_records(d)
    out += ["", "## 对话", ""]
    if not recs:
        out.append("（没有 transcript.jsonl）")
    for r in recs:
        t = r.get("type")
        if t == "system":
            out += ["### system（实际生效）", "", _fence(clip(r.get("text", ""))), ""]
        elif t == "message" and r.get("role") == "user":
            out += [f"### user · {r.get('ts', '')}{' · 更早的 attempt' if r.get('scope') == 'earlier_attempt' else ''}", "", _fence(clip(r.get("text", ""))), ""]
        elif t == "message" and r.get("role") == "assistant":
            u = r.get("usage") or {}
            out.append(f"### assistant · {r.get('provider')}/{r.get('model')} · {r.get('ts', '')}")
            out.append(f"stop={r.get('stop_reason')} · latency={r.get('latency_ms')}ms · tokens in={u.get('input')} out={u.get('output')} cache_r={u.get('cache_read')} cache_w={u.get('cache_write')}")
            if r.get("error"):
                out.append(f"**错误**：{r['error']}")
            for th in r.get("thinking") or []:
                out += ["", "<details><summary>thinking</summary>", "", clip(th.get("text", "（已被提供方脱敏）")), "", "</details>"]
            if r.get("text"):
                out += ["", clip(r["text"])]
            for c in r.get("tool_calls") or []:
                out += ["", f"→ 工具调用 `{c.get('name')}` (`{c.get('id')}`)", _fence(clip(json.dumps(c.get("arguments"), ensure_ascii=False, indent=2)), "json")]
            out.append("")
        elif t == "tool_result":
            flag = "❌ " if r.get("is_error") else ""
            out += [f"← {flag}工具结果 `{r.get('tool_name')}` (`{r.get('tool_call_id')}`) · {r.get('duration_ms')}ms"
                    + (f" · 大内容见 {r['_blob']}" if r.get("_blob") else ""), _fence(clip(r.get("text", ""))), ""]
        elif t == "turn":
            out += [f"_turn {r.get('index')}: {r.get('status')} · {r.get('latency_ms')}ms{(' · ' + r['error']) if r.get('error') else ''}_", ""]
        elif t == "retry":
            out += [f"_自动重试 {r.get('phase')} attempt={r.get('attempt')} {r.get('error') or ''}_", ""]
        elif t == "summary":
            out += ["## 汇总", "", _fence(json.dumps(r, ensure_ascii=False, indent=2), "json"), ""]
    return "\n".join(out) + "\n"
