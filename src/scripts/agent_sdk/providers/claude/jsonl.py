"""Key-only Claude stream-json progress lines."""

from __future__ import annotations

from typing import Any

from ...progress import (
    format_assistant,
    format_error,
    format_tool_start,
    parse_json_line,
)


class ClaudeJsonlFormatter:
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
    if event_type == "result" and payload.get("is_error"):
        return format_error(payload.get("result") or payload.get("error") or "failed")
    if event_type != "assistant":
        return ""
    message = payload.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    lines: list[str] = []
    if isinstance(content, str) and content.strip():
        lines.append(format_assistant(content))
    elif isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = str(block.get("type") or "")
            if block_type == "tool_use":
                lines.append(
                    format_tool_start(
                        _claude_tool_name(block.get("name")),
                        block.get("input"),
                    )
                )
            elif block_type == "text":
                text = format_assistant(str(block.get("text") or ""))
                if text:
                    lines.append(text)
    return "\n".join(lines)


def _claude_tool_name(name: Any) -> str:
    raw = str(name or "tool")
    if not raw.startswith("mcp__"):
        return raw
    parts = raw.split("__")
    if len(parts) >= 3:
        return f"MCP {parts[1]}.{parts[2]}"
    if len(parts) == 2:
        return f"MCP {parts[1]}"
    return raw
