"""Tagged progress lines for orchestrator and worker sessions.

Display knobs live here so prefixes, clipping, and spacing can be changed
without touching per-provider JSONL parsers.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, TextIO

INLINE_LIMIT = 100
ASSISTANT_CLIP = 400
COMMAND_CLIP = 400
PRINT_TOOL_ARGS = True
BLANK_LINE_AFTER = True

_WRITE_TOOLS = frozenset(
    {"write", "edit", "strreplace", "str_replace", "apply_patch", "patch"}
)
_COMMAND_MARKERS = ("bash", "shell", "command", "命令")
_PATH_MARKERS = ("read", "write", "edit", "glob", "ls")
_PATTERN_MARKERS = ("grep", "find")
_SKIP_ARG_KEYS = frozenset(
    {
        "content",
        "contents",
        "old_string",
        "new_string",
        "old_text",
        "new_text",
        "aggregated_output",
        "output",
        "result",
        "stdout",
        "stderr",
    }
)
_ARG_KEYS = ("args", "arguments", "input", "params")
_PATH_KEYS = ("path", "file_path", "target", "target_file")
_COMMAND_KEYS = ("command", "cmd")

_progress_log: Path | None = None


class LineFormatter(Protocol):
    def consume(self, chunk: str) -> str:
        """Return display text for one stdout chunk. Empty means skip."""
        ...


def clock() -> str:
    return datetime.now().strftime("%H:%M:%S")


def orchestrator_tag(*, now: str | None = None) -> str:
    return f"orchestrator-{now or clock()}"


def session_tag(
    stage_id: str,
    role: str,
    worker: str,
    *,
    attempt: int = 0,
    now: str | None = None,
) -> str:
    stage = (stage_id or "session").strip() or "session"
    actor = (role or "worker").strip() or "worker"
    if attempt >= 1:
        actor = f"{actor}#{attempt}"
    name = (worker or "agent").strip() or "agent"
    return f"{stage}({actor})-{name}-{now or clock()}"


def format_tagged(
    tag: str,
    body: str = "",
    *,
    header_own_line: bool = False,
) -> str:
    prefix = f"[{tag}]"
    text = (body or "").rstrip("\r\n")
    if header_own_line:
        rendered = prefix + "\n" if not text else f"{prefix}\n{text}\n"
    elif not text:
        rendered = prefix + "\n"
    elif "\n" in text or len(prefix) + 1 + len(text) > INLINE_LIMIT:
        rendered = f"{prefix}\n{text}\n"
    else:
        rendered = f"{prefix} {text}\n"
    if BLANK_LINE_AFTER and not rendered.endswith("\n\n"):
        rendered += "\n"
    return rendered


def set_progress_log(path: Path | str | None, *, append: bool = False) -> None:
    """Mirror tagged terminal lines to a UTF-8 file. None disables the log."""
    global _progress_log
    if path is None:
        _progress_log = None
        return
    target = Path(path)
    if target.exists() and target.is_dir():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if append:
        target.touch(exist_ok=True)
    else:
        target.write_text("", encoding="utf-8")
    _progress_log = target


def _append_progress_log(text: str) -> None:
    if _progress_log is None or not text:
        return
    try:
        with _progress_log.open("a", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
    except OSError:
        return


def print_tagged(
    tag: str,
    body: str = "",
    *,
    header_own_line: bool = False,
    file: TextIO | None = None,
) -> None:
    rendered = format_tagged(tag, body, header_own_line=header_own_line)
    print(rendered, end="", file=file, flush=True)
    _append_progress_log(rendered)


def print_orchestrator(body: str, *, file: TextIO | None = None) -> None:
    print_tagged(orchestrator_tag(), body, file=file)


def print_session(
    stage_id: str,
    role: str,
    worker: str,
    body: str,
    *,
    attempt: int = 0,
    file: TextIO | None = None,
) -> None:
    if not stage_id and not role:
        return
    print_tagged(
        session_tag(stage_id, role, worker, attempt=attempt),
        body,
        header_own_line=True,
        file=file,
    )


def clip_text(text: str, limit: int = ASSISTANT_CLIP) -> str:
    stripped = (text or "").strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[:limit].rstrip() + "…"


def parse_json_line(line: str) -> dict[str, Any] | None:
    stripped = (line or "").strip()
    if not stripped.startswith("{"):
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def tool_args_from(*objs: Any) -> dict[str, Any]:
    for obj in objs:
        if not isinstance(obj, dict):
            continue
        for key in _ARG_KEYS:
            value = obj.get(key)
            if isinstance(value, dict):
                return value
    return {}


def tool_arg_summary(name: str, args: Any) -> str:
    if not PRINT_TOOL_ARGS:
        return ""
    data = args if isinstance(args, dict) else {}
    if not data:
        return ""
    lower = _tool_key(name)
    if any(marker in lower for marker in _COMMAND_MARKERS):
        text = _first_str(data, _COMMAND_KEYS)
        if text:
            return clip_text(text.replace("\n", " "), COMMAND_CLIP)
    if any(marker in lower for marker in _PATH_MARKERS):
        path = _first_str(data, _PATH_KEYS)
        if path:
            return clip_text(path, COMMAND_CLIP)
    if any(marker in lower for marker in _PATTERN_MARKERS):
        pattern = _first_str(data, ("pattern", "query"))
        path = _first_str(data, _PATH_KEYS)
        joined = " ".join(part for part in (pattern, path) if part)
        if joined:
            return clip_text(joined, COMMAND_CLIP)
    for key, value in data.items():
        if key in _SKIP_ARG_KEYS or value in (None, "", {}, []):
            continue
        if isinstance(value, dict | list):
            continue
        text = str(value).replace("\n", " ").strip()
        if text:
            return clip_text(text, COMMAND_CLIP)
    return ""


def format_tool_start(name: str, args: Any = None) -> str:
    detail = tool_arg_summary(name, args)
    if detail:
        return f"→ {name} {detail}"
    return f"→ {name}"


def format_tool_end(name: str, args: Any = None, *, error: Any = None) -> str:
    if error:
        detail = error.get("message") if isinstance(error, dict) else error
        return f"✗ {name}: {detail}"
    if _is_write_tool(name):
        path = tool_arg_summary(name, args)
        return f"✓ 写入 {path}".rstrip() if path else "✓ 写入"
    return f"✓ {name}"


def format_assistant(text: str) -> str:
    return clip_text(text, ASSISTANT_CLIP)


def format_error(detail: Any) -> str:
    if isinstance(detail, dict):
        detail = detail.get("message") or detail
    return f"error: {detail}"


def _tool_key(name: str) -> str:
    raw = (name or "").strip().lower()
    if raw.startswith("mcp "):
        raw = raw.split()[-1]
    if "." in raw:
        raw = raw.rsplit(".", 1)[-1]
    return raw


def _is_write_tool(name: str) -> bool:
    key = _tool_key(name)
    return key in _WRITE_TOOLS or "写入" in (name or "")


def _first_str(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if value not in (None, "", {}, []):
            return str(value)
    return ""
