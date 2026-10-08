"""Detect model/API transport failures from worker CLI stdout/stderr."""

from __future__ import annotations

from typing import Any

from core.contracts.session import SessionError

from .progress import parse_json_line

_TRANSPORT_MARKERS = (
    "connection error",
    "connect timeout",
    "connection refused",
    "econnrefused",
    "etimedout",
    "network error",
    "rate limit",
    "too many requests",
    "authentication",
    "api key",
    "unauthorized",
    "401",
    "429",
    "502",
    "503",
    "504",
    "bad gateway",
    "service unavailable",
    "gateway timeout",
    "ssl",
    "tls",
    "certificate",
)


class WorkerTransportError(SessionError):
    """Worker turn failed before substantive model output (retryable)."""


def detect_worker_transport_failure(
    worker: str,
    stdout: str,
    stderr: str = "",
    *,
    returncode: int = 0,
) -> str | None:
    """Return a short detail string if the turn looks like a transport/API failure."""
    name = (worker or "").strip().lower()
    out = stdout or ""
    err = stderr or ""
    if _has_substantive_progress(name, out):
        return None
    detail = _detect_structured(name, out)
    if detail:
        return detail
    combined = f"{err}\n{out}".lower()
    if _matches_transport_marker(combined):
        snippet = _first_matching_line(err or out) or "network or API error"
        return _clip(snippet)
    if returncode != 0 and _matches_transport_marker(combined):
        return _clip(_first_matching_line(err or out) or f"exit {returncode}")
    return None


def is_worker_transport_error(exc: BaseException) -> bool:
    return isinstance(exc, WorkerTransportError)


def _clip(text: str, limit: int = 240) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def _matches_transport_marker(text: str) -> bool:
    lower = text.lower()
    return any(marker in lower for marker in _TRANSPORT_MARKERS)


def _first_matching_line(blob: str) -> str:
    for line in blob.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _matches_transport_marker(stripped):
            return stripped
    return ""


def _iter_json_objects(blob: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw in blob.splitlines():
        payload = parse_json_line(raw)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _has_substantive_progress(worker: str, stdout: str) -> bool:
    events = _iter_json_objects(stdout)
    if not events:
        return False
    if worker == "pi":
        return _pi_has_progress(events)
    if worker == "codex":
        return _codex_has_progress(events)
    if worker == "claude":
        return _claude_has_progress(events)
    if worker == "opencode":
        return _opencode_has_progress(events)
    return _generic_has_progress(events)


def _assistant_text_from_message(message: Any) -> str:
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
        joined = "".join(parts).strip()
        if joined:
            return joined
    text = message.get("text")
    return str(text).strip() if text else ""


def _pi_has_progress(events: list[dict[str, Any]]) -> bool:
    for payload in events:
        event_type = str(payload.get("type") or "")
        if event_type in {"tool_execution_end", "tool_end", "tool_call_end", "tool.end"}:
            if not payload.get("error"):
                return True
        if event_type in {"message_end", "turn_end", "agent_end"}:
            message = payload.get("message")
            if _assistant_text_from_message(message):
                return True
            if event_type == "agent_end":
                for item in payload.get("messages") or []:
                    if _assistant_text_from_message(item):
                        return True
    return False


def _codex_has_progress(events: list[dict[str, Any]]) -> bool:
    for payload in events:
        event_type = str(payload.get("type") or "")
        if event_type == "item.completed":
            item = payload.get("item")
            if isinstance(item, dict) and str(item.get("type") or "") == "agent_message":
                text = item.get("text") or ""
                if str(text).strip():
                    return True
        if event_type in {"item.started", "item.completed"}:
            item = payload.get("item")
            if isinstance(item, dict) and str(item.get("type") or "") == "tool_call":
                return True
    return False


def _claude_has_progress(events: list[dict[str, Any]]) -> bool:
    for payload in events:
        if str(payload.get("type") or "") != "assistant":
            continue
        message = payload.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    return True
                if block.get("type") == "text" and str(block.get("text") or "").strip():
                    return True
    return False


def _opencode_has_progress(events: list[dict[str, Any]]) -> bool:
    for payload in events:
        event_type = str(payload.get("type") or "")
        if event_type == "text":
            if _part_text_opencode(payload):
                return True
        if event_type in {"tool_result", "tool_end", "tool.end", "tool_complete"}:
            return True
        if event_type == "tool":
            part = payload.get("part")
            if isinstance(part, dict) and str(part.get("type") or "") == "tool":
                state = part.get("state")
                if isinstance(state, dict) and str(state.get("status") or "").lower() in {
                    "completed",
                    "complete",
                    "success",
                }:
                    return True
    return False


def _part_text_opencode(payload: dict[str, Any]) -> str:
    part = payload.get("part")
    if isinstance(part, dict):
        text = part.get("text")
        if text:
            return str(text).strip()
    text = payload.get("text")
    return str(text).strip() if text else ""


def _generic_has_progress(events: list[dict[str, Any]]) -> bool:
    for payload in events:
        if _assistant_text_from_message(payload.get("message")):
            return True
    return False


def _detect_structured(worker: str, stdout: str) -> str | None:
    events = _iter_json_objects(stdout)
    if worker == "pi":
        return _detect_pi(events)
    if worker == "codex":
        return _detect_codex(events)
    if worker == "claude":
        return _detect_claude(events)
    if worker == "opencode":
        return _detect_opencode(events)
    return None


def _detect_pi(events: list[dict[str, Any]]) -> str | None:
    for payload in events:
        event_type = str(payload.get("type") or "")
        if event_type == "auto_retry_end" and payload.get("success") is False:
            detail = payload.get("finalError") or payload.get("errorMessage") or "retry failed"
            return _clip(str(detail))
        if event_type in {"turn_end", "message_end"}:
            message = payload.get("message")
            if isinstance(message, dict) and str(message.get("stopReason") or "") == "error":
                detail = message.get("errorMessage") or message.get("error") or "model error"
                return _clip(str(detail))
    return None


def _detect_codex(events: list[dict[str, Any]]) -> str | None:
    for payload in events:
        event_type = str(payload.get("type") or "")
        if event_type == "error":
            detail = payload.get("message") or payload.get("error") or payload
            return _clip(str(detail))
        if event_type == "turn.failed":
            detail = payload.get("error") or payload.get("message") or payload
            return _clip(str(detail))
    return None


def _detect_claude(events: list[dict[str, Any]]) -> str | None:
    for payload in events:
        event_type = str(payload.get("type") or "")
        if event_type == "error":
            detail = payload.get("error") or payload.get("message") or payload
            return _clip(str(detail))
        if event_type == "result" and payload.get("is_error"):
            detail = payload.get("result") or payload.get("error") or "failed"
            return _clip(str(detail))
    return None


def _detect_opencode(events: list[dict[str, Any]]) -> str | None:
    saw_tool_failure = False
    for payload in events:
        event_type = str(payload.get("type") or "")
        if event_type == "error":
            detail = payload.get("error") or payload.get("message") or "error"
            return _clip(str(detail))
        part = payload.get("part")
        if isinstance(part, dict):
            state = part.get("state")
            if isinstance(state, dict):
                status = str(state.get("status") or "").lower()
                if status in {"error", "failed"}:
                    saw_tool_failure = True
    if saw_tool_failure:
        return "tool execution failed before model response"
    return None


def scan_archived_stdout_for_transport(
    worker: str,
    stdout_path: str,
) -> str | None:
    try:
        from pathlib import Path

        text = Path(stdout_path).read_text(encoding="utf-8")
    except OSError:
        return None
    return detect_worker_transport_failure(worker, text, "")
