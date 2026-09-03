"""Turn Codex Python SDK notifications into readable orchestrator lines."""

from __future__ import annotations

import json
from typing import Any, Callable


MAX_OUTPUT_CHARS = 8_000
MAX_REASONING_CHARS = 800
MAX_PROMPT_CHARS = 400
MAX_ARGS_CHARS = 400

_SKIP_METHODS = frozenset(
    {
        "thread/started",
        "thread.started",
        "turn/started",
        "turn.started",
        "turn/completed",
        "turn.completed",
    }
)
_ITEM_STARTED = frozenset({"item/started", "item.started"})
_ITEM_COMPLETED = frozenset({"item/completed", "item.completed"})
_ITEM_UPDATED = frozenset({"item/updated", "item.updated"})
_ERROR_METHODS = frozenset({"error", "turn/failed", "turn.failed"})
_COLLAB_LABELS = {
    "spawn_agent": "委派子 Agent",
    "wait": "等待子 Agent",
    "send_input": "向子 Agent 发送输入",
    "close_agent": "关闭子 Agent",
    "resume_agent": "恢复子 Agent",
}


class CodexEventFormatter:
    """Format one SDK notification at a time, collapsing wait heartbeats."""

    def __init__(self) -> None:
        self._waiting = False

    def consume(self, event: object) -> str:
        return format_codex_event(event, waiting=self._waiting, on_wait=self._mark_wait)

    def _mark_wait(self, waiting: bool) -> None:
        self._waiting = waiting


def format_codex_event(
    event: object,
    *,
    waiting: bool = False,
    on_wait: Callable[[bool], None] | None = None,
) -> str:
    """Return display text for one Codex SDK event. Empty string means skip."""
    method = _method_of(event)
    payload = _payload_of(event)
    payload_dict = _as_dict(payload)

    if _should_skip_method(method):
        return ""
    if method in _ERROR_METHODS:
        return _format_error(payload, payload_dict)
    if method in _ITEM_UPDATED:
        return ""
    if method in _ITEM_STARTED or method in _ITEM_COMPLETED:
        item = _item_dict(payload, payload_dict)
        if not item:
            return ""
        text = _format_item(
            item,
            started=method in _ITEM_STARTED,
            waiting=waiting,
            on_wait=on_wait,
        )
        if text:
            return text
        if text == "":
            return ""
        kind = _item_kind(item)
        if kind:
            return f"{method} {kind}"
        return ""
    item = _item_dict(payload, payload_dict)
    kind = _item_kind(item)
    if method and kind:
        return f"{method} {kind}"
    return ""


def _should_skip_method(method: str) -> bool:
    if not method:
        return False
    if method in _SKIP_METHODS:
        return True
    lowered = method.lower()
    if "delta" in lowered:
        return True
    compact = lowered.replace("_", "").replace("/", "").replace(".", "")
    if "tokenusage" in compact:
        return True
    normalized = method.replace(".", "/")
    return normalized.startswith("account/")


def _method_of(event: object) -> str:
    if isinstance(event, dict):
        return str(event.get("method") or "")
    return str(getattr(event, "method", "") or "")


def _payload_of(event: object) -> object:
    if isinstance(event, dict):
        return event.get("payload", event)
    payload = getattr(event, "payload", None)
    if payload is not None:
        return payload
    return event


def _as_dict(value: object) -> dict[str, Any]:
    dumped = _dump(value)
    return dumped if isinstance(dumped, dict) else {}


def _dump(value: object) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _dump(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_dump(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump(mode="json")
        except TypeError:
            dumped = model_dump()
        return _dump(dumped)
    root = getattr(value, "root", None)
    if root is not None:
        dumped = _dump(root)
        if isinstance(dumped, dict):
            return dumped
    if hasattr(value, "__dict__"):
        return {
            key: _dump(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    enum_value = getattr(value, "value", None)
    if enum_value is not None and not isinstance(value, type):
        return _dump(enum_value)
    return value


def _item_dict(payload: object, payload_dict: dict[str, Any]) -> dict[str, Any]:
    raw = getattr(payload, "item", None) if payload is not None else None
    if raw is None:
        raw = payload_dict.get("item")
    dumped = _as_dict(raw) if not isinstance(raw, dict) else _dump(raw)
    if not isinstance(dumped, dict):
        return {}
    if "type" not in dumped and "item_type" not in dumped and "itemType" not in dumped:
        nested = dumped.get("root")
        if nested is not None:
            dumped = _as_dict(nested) if not isinstance(nested, dict) else nested
    return dumped if isinstance(dumped, dict) else {}


def _item_kind(item: dict[str, Any]) -> str:
    return str(item.get("type") or item.get("item_type") or item.get("itemType") or "")


def _normalize_kind(kind: str) -> str:
    if not kind:
        return ""
    if "_" in kind or kind.islower():
        return kind
    chars: list[str] = []
    for index, char in enumerate(kind):
        if char.isupper() and index:
            chars.append("_")
        chars.append(char.lower())
    return "".join(chars)


def _format_error(payload: object, payload_dict: dict[str, Any]) -> str:
    error = getattr(payload, "error", None) if payload is not None else None
    if error is None:
        error = payload_dict.get("error") or payload_dict.get("message")
    dumped = _as_dict(error) if not isinstance(error, dict) else error
    if isinstance(dumped, dict) and dumped:
        message = dumped.get("message") or dumped.get("error") or dumped
    else:
        message = error if error not in (None, "") else payload_dict.get("message")
    if message in (None, "", {}):
        return "error"
    return f"error: {message}"


def _format_item(
    item: dict[str, Any],
    *,
    started: bool,
    waiting: bool,
    on_wait: Callable[[bool], None] | None,
) -> str | None:
    kind = _normalize_kind(_item_kind(item))

    if kind in {"agent_message", "assistant_message"}:
        if started:
            return ""
        return str(item.get("text") or "").strip()

    if kind == "reasoning":
        if started:
            return ""
        text = _reasoning_text(item)
        if not text:
            return ""
        return f"思考: {_clip(text, MAX_REASONING_CHARS)}"

    if kind == "command_execution":
        command = item.get("command") or ""
        if started:
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
        if started:
            _set_wait(on_wait, False)
            arguments = item.get("arguments")
            suffix = ""
            if arguments not in (None, "", {}):
                rendered = _compact(arguments)
                if rendered:
                    suffix = f" {_clip(rendered, MAX_ARGS_CHARS)}"
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
        normalized_tool = _normalize_kind(tool_name)
        label = _COLLAB_LABELS.get(normalized_tool, f"协作 {tool_name}")
        is_wait = normalized_tool in {"wait", "resume_agent"}
        if started:
            if is_wait:
                if waiting:
                    return ""
                _set_wait(on_wait, True)
                return f"→ {label}"
            _set_wait(on_wait, False)
            prompt = str(item.get("prompt") or "").strip()
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
        if started:
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

    if kind == "web_search":
        query = str(item.get("query") or "").strip()
        if started:
            return f"→ 搜索: {query}" if query else "→ 搜索"
        return f"✓ 搜索: {query}" if query else "✓ 搜索"

    if kind == "dynamic_tool_call":
        tool = item.get("tool") or "?"
        if started:
            return f"→ 工具: {tool}"
        status = item.get("status") or "completed"
        return f"✓ 工具: {tool} ({status})"

    if kind == "plan":
        if started:
            return ""
        text = str(item.get("text") or "").strip()
        if not text:
            return "✓ 计划"
        return f"✓ 计划: {_clip(text.replace(chr(10), ' '), MAX_PROMPT_CHARS)}"

    if kind == "error":
        return f"error: {item.get('message') or item}"
    return None


def _reasoning_text(item: dict[str, Any]) -> str:
    text = str(item.get("text") or "").strip()
    if text:
        return text
    parts: list[str] = []
    for key in ("summary", "content"):
        value = item.get(key)
        if isinstance(value, list):
            parts.extend(str(part).strip() for part in value if str(part).strip())
        elif isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return "\n".join(parts)


def _format_mcp_result(result: Any) -> str:
    if result in (None, "", {}, []):
        return ""
    if isinstance(result, str):
        return result
    dumped = _as_dict(result) if not isinstance(result, dict) else result
    if not isinstance(dumped, dict):
        return str(result)
    content = dumped.get("content")
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
    structured = dumped.get("structured_content") or dumped.get("structuredContent")
    if structured not in (None, "", {}):
        return json.dumps(structured, ensure_ascii=False, default=str)
    return json.dumps(dumped, ensure_ascii=False, default=str)


def _format_agents_states(states: Any) -> str:
    if not states:
        return ""
    if isinstance(states, str):
        return states
    dumped = _as_dict(states) if not isinstance(states, dict) else states
    if isinstance(dumped, dict):
        lines = []
        for thread_id, state in dumped.items():
            state_dict = _as_dict(state) if not isinstance(state, dict) else state
            if isinstance(state_dict, dict):
                status = state_dict.get("status") or state_dict.get("state") or ""
                message = (
                    state_dict.get("message")
                    or state_dict.get("last_message")
                    or state_dict.get("summary")
                    or ""
                )
                detail = " ".join(part for part in (str(status), str(message)) if part)
                lines.append(f"{thread_id}: {detail}".rstrip(": "))
            else:
                lines.append(f"{thread_id}: {state}")
        return "\n".join(lines)
    return str(states)


def _compact(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n…(truncated)"


def _set_wait(on_wait: Callable[[bool], None] | None, waiting: bool) -> None:
    if callable(on_wait):
        on_wait(waiting)
