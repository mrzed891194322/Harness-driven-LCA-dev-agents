"""Key-only OpenCode JSONL progress lines."""

from __future__ import annotations

from typing import Any

from ...progress import (
    format_assistant,
    format_error,
    format_tool_end,
    format_tool_start,
    parse_json_line,
    tool_args_from,
)

_SKIP_TYPES = frozenset(
    {
        "step_start",
        "step.start",
        "step_finish",
        "step_end",
        "step.finish",
        "session",
        "idle",
    }
)
_START_TYPES = frozenset({"tool", "tool_use", "tool_call", "tool_start", "tool.start"})
_END_TYPES = frozenset(
    {"tool_result", "tool_end", "tool.end", "tool_complete", "tool.complete"}
)


class OpenCodeJsonlFormatter:
    def consume(self, chunk: str) -> str:
        payload = parse_json_line(chunk)
        if payload is None:
            return ""
        text = _format_event(payload)
        if not text:
            return ""
        return text if text.endswith("\n") else text + "\n"


def _format_event(payload: dict[str, Any]) -> str:
    event_type = str(payload.get("type") or "")
    if event_type in _SKIP_TYPES:
        return ""
    if event_type == "error":
        return format_error(payload.get("error") or payload.get("message") or "error")
    if event_type == "text":
        text = _part_text(payload)
        return format_assistant(text) if text else ""
    raw_part = payload.get("part")
    part = raw_part if isinstance(raw_part, dict) else {}
    tool = _tool_name(payload, part)
    raw_state = part.get("state")
    state = raw_state if isinstance(raw_state, dict) else {}
    status = str(state.get("status") or payload.get("status") or "").lower()
    part_type = str(part.get("type") or "")
    args = tool_args_from(payload, part, state)
    error = state.get("error") or payload.get("error")
    if event_type in _START_TYPES or part_type == "tool":
        if status in {"completed", "complete", "success", "finished"}:
            return format_tool_end(tool, args, error=error)
        if status in {"error", "failed"}:
            return format_tool_end(tool, args, error=error or "failed")
        return format_tool_start(tool, args)
    if event_type in _END_TYPES:
        return format_tool_end(tool, args, error=error)
    return ""


def _tool_name(payload: dict[str, Any], part: dict[str, Any]) -> str:
    raw = (
        payload.get("tool")
        or payload.get("name")
        or part.get("tool")
        or part.get("name")
        or "tool"
    )
    return str(raw)


def _part_text(payload: dict[str, Any]) -> str:
    part = payload.get("part")
    if isinstance(part, dict):
        text = part.get("text")
        if text:
            return str(text).strip()
    text = payload.get("text")
    return str(text).strip() if text else ""
