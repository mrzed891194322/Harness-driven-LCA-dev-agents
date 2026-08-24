"""Translate Codex `exec --json` JSONL events into readable GUI terminal lines."""

from __future__ import annotations

import json
from typing import Any


MAX_OUTPUT_CHARS = 8_000
MAX_REASONING_CHARS = 800
MAX_PROMPT_CHARS = 400

_SKIP_EVENT_TYPES = frozenset(
    {"thread.started", "turn.started", "turn.completed"}
)
_COLLAB_LABELS = {
    "spawn_agent": "委派子 Agent",
    "SpawnAgent": "委派子 Agent",
    "wait": "等待子 Agent",
    "Wait": "等待子 Agent",
    "send_input": "向子 Agent 发送输入",
    "SendInput": "向子 Agent 发送输入",
    "close_agent": "关闭子 Agent",
    "CloseAgent": "关闭子 Agent",
    "resume_agent": "恢复子 Agent",
    "ResumeAgent": "恢复子 Agent",
}


class CodexJsonlFormatter:
    """Convert one JSONL event at a time, skipping duplicate wait heartbeats."""

    def __init__(self) -> None:
        self._waiting = False

    def consume(self, chunk: str) -> str:
        if not chunk:
            return ""
        return format_codex_stream_line(chunk, waiting=self._waiting, on_wait=self._mark_wait)

    def _mark_wait(self, waiting: bool) -> None:
        self._waiting = waiting


def format_codex_stream_line(
    line: str,
    *,
    waiting: bool = False,
    on_wait: Any | None = None,
) -> str:
    """Return display text for one stdout line. Empty string means skip."""
    raw = line.rstrip("\r\n")
    if not raw.strip():
        return ""
    stripped = raw.lstrip()
    if not stripped.startswith("{"):
        return raw + "\n"
    try:
        event = json.loads(stripped)
    except json.JSONDecodeError:
        return raw + "\n"
    if not isinstance(event, dict):
        return ""
    text = _format_event(event, waiting=waiting, on_wait=on_wait)
    if not text:
        return ""
    return text if text.endswith("\n") else text + "\n"


def _format_event(
    event: dict[str, Any],
    *,
    waiting: bool,
    on_wait: Any | None,
) -> str:
    event_type = str(event.get("type") or "")
    if event_type in _SKIP_EVENT_TYPES:
        return ""
    if event_type == "error":
        return f"[Codex error] {event.get('message') or event.get('error') or event}"
    if event_type == "turn.failed":
        return f"[Codex] turn failed: {event.get('error') or event.get('message') or event}"
    if event_type in {"item.started", "item.updated", "item.completed"}:
        item = event.get("item")
        if not isinstance(item, dict):
            return ""
        return _format_item(item, event_type, waiting=waiting, on_wait=on_wait)
    return ""


def _format_item(
    item: dict[str, Any],
    event_type: str,
    *,
    waiting: bool,
    on_wait: Any | None,
) -> str:
    kind = str(item.get("type") or item.get("item_type") or item.get("itemType") or "")
    if event_type == "item.updated":
        return ""

    if kind in {"agent_message", "assistant_message"}:
        if event_type != "item.completed":
            return ""
        return (item.get("text") or "").strip()

    if kind == "reasoning":
        if event_type != "item.completed":
            return ""
        text = (item.get("text") or "").strip()
        if not text:
            return ""
        return f"思考: {_clip(text, MAX_REASONING_CHARS)}"

    if kind == "command_execution":
        command = item.get("command") or ""
        if event_type == "item.started":
            _set_wait(on_wait, False)
            return f"→ 命令: {command}"
        exit_code = item.get("exit_code", item.get("exitCode"))
        status = item.get("status") or "completed"
        header = (
            f"✓ 命令结束 (exit {exit_code})"
            if exit_code is not None
            else f"✓ 命令结束 ({status})"
        )
        output = (
            item.get("aggregated_output")
            or item.get("aggregatedOutput")
            or item.get("output")
            or ""
        )
        if str(output).strip():
            return f"{header}\n{_clip(str(output).rstrip(), MAX_OUTPUT_CHARS)}"
        return header

    if kind == "mcp_tool_call":
        server = item.get("server") or "?"
        tool = item.get("tool") or "?"
        if event_type == "item.started":
            _set_wait(on_wait, False)
            arguments = item.get("arguments")
            suffix = f" {arguments}" if arguments not in (None, "", {}) else ""
            return f"→ MCP {server}.{tool}{suffix}"
        error = item.get("error")
        if isinstance(error, dict):
            error = error.get("message") or error
        status = item.get("status") or "completed"
        line = (
            f"✗ MCP {server}.{tool}: {error}"
            if error
            else f"✓ MCP {server}.{tool} ({status})"
        )
        result_text = _format_mcp_result(item.get("result"))
        if result_text:
            return f"{line}\n{_clip(result_text, MAX_OUTPUT_CHARS)}"
        return line

    if kind in {"collab_tool_call", "collab_agent_tool_call"}:
        tool_name = str(item.get("tool") or "collab")
        label = _COLLAB_LABELS.get(tool_name, f"协作 {tool_name}")
        is_wait = tool_name.lower() in {"wait", "resumeagent", "resume_agent"}
        if event_type == "item.started":
            if is_wait:
                if waiting:
                    return ""
                _set_wait(on_wait, True)
                return f"→ {label}"
            _set_wait(on_wait, False)
            prompt = (item.get("prompt") or "").strip()
            receivers = (
                item.get("receiver_thread_ids") or item.get("receiverThreadIds") or []
            )
            parts = [f"→ {label}"]
            if receivers:
                parts.append(f"threads={receivers}")
            if prompt:
                parts.append(_clip(prompt.replace("\n", " "), MAX_PROMPT_CHARS))
            return " ".join(parts)
        _set_wait(on_wait, False)
        summary = _format_agents_states(
            item.get("agents_states") or item.get("agentsStates")
        )
        if summary:
            return f"✓ {label}\n{summary}"
        return f"✓ {label}"

    if kind == "file_change":
        if event_type != "item.completed":
            return ""
        paths: list[str] = []
        for change in item.get("changes") or []:
            if isinstance(change, dict):
                paths.append(str(change.get("path") or change))
            else:
                paths.append(str(change))
        if not paths:
            return "✓ 写入文件"
        return "✓ 写入: " + ", ".join(paths[:20])

    if kind == "error":
        return f"[Codex item error] {item.get('message') or item}"
    return ""


def _set_wait(on_wait: Any | None, waiting: bool) -> None:
    if callable(on_wait):
        on_wait(waiting)


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n…(truncated)"


def _format_mcp_result(result: Any) -> str:
    if result in (None, "", {}, []):
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict) and block.get("text"):
                    parts.append(str(block["text"]))
                else:
                    parts.append(str(block))
            if parts:
                return "\n".join(parts)
        structured = result.get("structured_content") or result.get("structuredContent")
        if structured not in (None, "", {}):
            return json.dumps(structured, ensure_ascii=False, default=str)
    return json.dumps(result, ensure_ascii=False, default=str)


def _format_agents_states(states: Any) -> str:
    if not states:
        return ""
    if isinstance(states, str):
        return states
    if isinstance(states, dict):
        lines = []
        for thread_id, state in states.items():
            if isinstance(state, dict):
                status = state.get("status") or state.get("state") or ""
                message = (
                    state.get("message")
                    or state.get("last_message")
                    or state.get("summary")
                    or ""
                )
                detail = " ".join(part for part in (str(status), str(message)) if part)
                lines.append(f"{thread_id}: {detail}".rstrip(": "))
            else:
                lines.append(f"{thread_id}: {state}")
        return "\n".join(lines)
    return str(states)
