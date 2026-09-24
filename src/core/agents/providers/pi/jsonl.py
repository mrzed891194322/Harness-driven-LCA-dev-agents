"""Key-only Pi JSONL progress lines."""

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

_START_TYPES = frozenset(
    {
        "tool_execution_start",
        "tool_start",
        "tool_call_start",
        "tool.start",
    }
)
_END_TYPES = frozenset(
    {
        "tool_execution_end",
        "tool_end",
        "tool_call_end",
        "tool.end",
    }
)
_TEXT_TYPES = frozenset({"message_end", "turn_end", "agent_end"})


class PiJsonlFormatter:
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
    if event_type == "error":
        return format_error(payload.get("error") or payload.get("message") or payload)
    if event_type == "auto_retry_end" and payload.get("success") is False:
        detail = payload.get("finalError") or payload.get("errorMessage") or "retry failed"
        return format_error(f"模型连接失败: {detail}")
    if event_type in {"turn_end", "message_end"}:
        message = payload.get("message")
        if isinstance(message, dict) and str(message.get("stopReason") or "") == "error":
            detail = message.get("errorMessage") or message.get("error") or "model error"
            return format_error(f"模型连接失败: {detail}")
        if event_type in _TEXT_TYPES:
            text = _message_text(message)
            return format_assistant(text) if text else ""
    args = tool_args_from(payload)
    if event_type in _START_TYPES:
        return format_tool_start(_tool_name(payload), args)
    if event_type in _END_TYPES:
        return format_tool_end(_tool_name(payload), args, error=payload.get("error"))
    if event_type in _TEXT_TYPES:
        text = _message_text(payload.get("message"))
        if not text and event_type == "agent_end":
            for item in payload.get("messages") or []:
                text = _message_text(item)
                if text:
                    break
        return format_assistant(text) if text else ""
    return ""


def _tool_name(payload: dict[str, Any]) -> str:
    return str(
        payload.get("toolName") or payload.get("tool") or payload.get("name") or "tool"
    )


def _message_text(message: Any) -> str:
    if isinstance(message, str) and message.strip():
        return message.strip()
    if not isinstance(message, dict):
        return ""
    if str(message.get("role") or "") not in {"", "assistant"}:
        return ""
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict):
                text = item.get("text") or item.get("delta")
                if text:
                    parts.append(str(text))
        return "".join(parts).strip()
    text = message.get("text")
    return str(text).strip() if text else ""
