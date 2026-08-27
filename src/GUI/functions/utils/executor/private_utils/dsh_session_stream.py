"""Tail DSH session JSONL logs and format events for the GUI terminal."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Generator, Iterator

MAX_TEXT_CHARS = 2_000
MAX_ARGS_CHARS = 400
_SKIP_EVENT_TYPES = frozenset(
    {
        "session",
        "permission/preset",
        "sandbox/mode",
        "approval/policy",
        "agent/inbox/spliced",
        "request/header",
        "request/context",
        "session/title",
        "session/end-seed",
        "user/message",
        "step/start",
        "step/end",
        "usage",
        "finish",
        "block-start",
        "text",
        "text-delta",
        "text-chunks",
        "reasoning",
        "reasoning-delta",
        "reasoning-chunks",
        "tool-call",
        "tool-call-delta",
        "tool-call-chunks",
    }
)
_SYSTEM_REMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)


def dsh_home() -> Path:
    return Path(os.environ.get("DSH_HOME", Path.home() / ".dsh")).expanduser()


def sessions_root() -> Path:
    return dsh_home() / "sessions"


def project_key(cwd: str) -> str:
    """Mirror @deepseek-ai/dsh-session-persistence-jsonl projectKey()."""
    if not cwd:
        raise ValueError("cannot encode an empty project path")
    readable: list[str] = []
    separator_run = False
    for ch in cwd:
        if ch in ("/", "\\", ":"):
            if not separator_run:
                readable.append("-")
            separator_run = True
        elif ch != "~" and re.fullmatch(r"[A-Za-z0-9._-]", ch):
            readable.append(ch)
            separator_run = False
        else:
            readable.append(f"~{ord(ch):04X}")
            separator_run = False
    body = "".join(readable).lstrip("-") or "root"
    return f"--{body[:251]}--"


def _relevant_project_dirs(sessions_root_path: Path, project_root: Path) -> list[Path]:
    if not sessions_root_path.is_dir():
        return []
    key = project_key(str(project_root.resolve()))
    inner = key[2:-2]
    dirs: list[Path] = []
    for entry in sessions_root_path.iterdir():
        if not entry.is_dir():
            continue
        name = entry.name
        if inner in name or key in name:
            dirs.append(entry)
    return dirs


def _session_log_paths(project_dirs: list[Path]) -> list[Path]:
    logs: list[Path] = []
    for project_dir in project_dirs:
        if not project_dir.is_dir():
            continue
        for session_dir in project_dir.iterdir():
            if not session_dir.is_dir():
                continue
            zstd_path = session_dir / "session.jsonl.zstd"
            plain_path = session_dir / "session.jsonl"
            if zstd_path.is_file():
                logs.append(zstd_path)
            elif plain_path.is_file():
                logs.append(plain_path)
    return logs


def _decompress_log(path: Path) -> str:
    if path.name.endswith(".zstd"):
        zstd = shutil.which("zstd")
        if zstd is None:
            return ""
        result = subprocess.run(
            [zstd, "-d", "-c", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            return ""
        return result.stdout
    return path.read_text(encoding="utf-8", errors="replace")


def _message_text(content: Any) -> str:
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "text":
            continue
        text = str(block.get("text") or "")
        text = _SYSTEM_REMINDER_RE.sub("", text).strip()
        if text:
            parts.append(text)
    joined = "\n".join(parts).strip()
    if len(joined) > MAX_TEXT_CHARS:
        return joined[:MAX_TEXT_CHARS] + "…"
    return joined


def format_dsh_event(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or "")
    if event_type in _SKIP_EVENT_TYPES:
        return ""
    data = event.get("data")
    if not isinstance(data, dict):
        data = {}

    if event_type == "tool/call":
        name = str(data.get("name") or "tool")
        args = str(data.get("arguments") or "")
        if len(args) > MAX_ARGS_CHARS:
            args = args[:MAX_ARGS_CHARS] + "…"
        return f"[DSH tool] {name} {args}".strip()

    if event_type == "assistant/message":
        message = data.get("message")
        if not isinstance(message, dict):
            return ""
        text = _message_text(message.get("content"))
        if not text:
            return ""
        return f"[DSH assistant] {text}"

    if event_type == "turn/start":
        turn = data.get("turn")
        return f"[DSH] turn {turn} started"

    if event_type == "turn/end":
        turn = data.get("turn")
        reason = data.get("reason")
        reason_text = ""
        if isinstance(reason, dict):
            reason_text = str(reason.get("kind") or reason)
        return f"[DSH] turn {turn} ended ({reason_text or 'done'})"

    if event_type == "todo/write":
        todos = data.get("todos")
        if not isinstance(todos, list):
            return ""
        lines = []
        for item in todos[:12]:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "")
            content = str(item.get("content") or "").strip()
            if content:
                lines.append(f"  - [{status}] {content}")
        if not lines:
            return ""
        return "[DSH todos]\n" + "\n".join(lines)

    return ""


class DshSessionLogTailer:
    """Poll DSH session logs for one project and yield newly formatted lines."""

    def __init__(self, project_root: Path, *, since: float | None = None) -> None:
        self._project_root = project_root.resolve()
        self._since = since if since is not None else time.time()
        self._line_offsets: dict[Path, int] = {}

    def poll(self) -> list[str]:
        root = sessions_root()
        project_dirs = _relevant_project_dirs(root, self._project_root)
        outputs: list[str] = []
        for log_path in _session_log_paths(project_dirs):
            try:
                mtime = log_path.stat().st_mtime
            except OSError:
                continue
            if mtime < self._since - 2:
                continue
            text = _decompress_log(log_path)
            if not text:
                continue
            lines = text.splitlines()
            start = self._line_offsets.get(log_path, 0)
            if start >= len(lines):
                continue
            for raw_line in lines[start:]:
                raw = raw_line.strip()
                if not raw:
                    continue
                if raw.startswith('{"type":"session"'):
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                formatted = format_dsh_event(event)
                if formatted:
                    outputs.append(formatted if formatted.endswith("\n") else formatted + "\n")
            self._line_offsets[log_path] = len(lines)
        return outputs


def stream_dsh_session_updates(
    project_root: Path,
    *,
    since: float | None = None,
    poll_interval: float = 0.75,
    should_stop: Any | None = None,
) -> Generator[str, None, None]:
    tailer = DshSessionLogTailer(project_root, since=since)
    while True:
        if should_stop and should_stop():
            break
        for line in tailer.poll():
            yield line
        yield from _sleep_chunks(poll_interval, should_stop)


def _sleep_chunks(
    seconds: float,
    should_stop: Any | None,
) -> Iterator[str]:
    end = time.time() + seconds
    while time.time() < end:
        if should_stop and should_stop():
            return
        time.sleep(min(0.15, end - time.time()))
