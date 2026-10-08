"""Detect model/API transport failures from Pi runtime stdout/stderr."""

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


def _generic_has_progress(events: list[dict[str, Any]]) -> bool:
    for payload in events:
        if _assistant_text_from_message(payload.get("message")):
            return True
    return False


def _detect_structured(worker: str, stdout: str) -> str | None:
    events = _iter_json_objects(stdout)
    if worker == "pi":
        return _detect_pi(events)
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
