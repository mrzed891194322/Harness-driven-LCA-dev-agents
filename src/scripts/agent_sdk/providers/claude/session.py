from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...archive import resolve_mcp_render_dir
from ...openlca_mcp_timeout import mcp_tool_timeout_sec
from ...permissions import CLAUDE_PERMISSION_MODE, claude_allowed_tools_flag
from ...progress import LineFormatter
from ...session import SessionConfig, SessionRef, SessionResumeError
from ..cli_base import CliRunResult, CliSessionProvider
from ..store import write_stdio_mcp_snippet
from .jsonl import ClaudeJsonlFormatter


class ClaudeSessionProvider(CliSessionProvider):
    worker = "claude"
    binary = "claude"

    def resume(self, ref: SessionRef, config: SessionConfig) -> SessionRef:
        saved = super().resume(ref, config)
        if not Path(saved.storage.get("dir", "")).is_dir():
            raise SessionResumeError("Claude 会话存储目录不存在")
        return saved

    def _assert_native_storage(self, ref: SessionRef, config: SessionConfig) -> None:
        del config
        if not Path(ref.storage.get("dir", "")).is_dir():
            raise SessionResumeError("Claude 会话存储目录不存在")

    def _create_storage(
        self,
        config: SessionConfig,
        storage_dir: Path,
        session_id: str,
    ) -> dict[str, str]:
        del session_id
        mcp_path = resolve_mcp_render_dir(config, storage_dir) / "mcp.json"
        write_claude_mcp(mcp_path, config.mcp_servers)
        return {"mcp_path": str(mcp_path) if config.mcp_servers else ""}

    def _prepare_turn(self, ref: SessionRef, config: SessionConfig) -> None:
        render_dir = resolve_mcp_render_dir(config, Path(ref.storage["dir"]))
        mcp_path = render_dir / "mcp.json"
        write_claude_mcp(mcp_path, config.mcp_servers)
        ref.storage["mcp_path"] = str(mcp_path) if config.mcp_servers else ""

    def build_command(
        self,
        binary: str,
        ref: SessionRef,
        prompt: str,
        config: SessionConfig,
    ) -> list[str]:
        argv = [
            binary,
            "-p",
            prompt,
            "--permission-mode",
            CLAUDE_PERMISSION_MODE,
            "--allowed-tools",
            claude_allowed_tools_flag(config.mcp_servers),
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        if config.model:
            argv.extend(["--model", config.model])
        mcp_path = ref.storage.get("mcp_path") or ""
        if mcp_path:
            argv.extend(["--mcp-config", mcp_path, "--strict-mcp-config"])
        native = ref.storage.get("claude_session_id") or ""
        if native:
            argv.extend(["--resume", native])
        return argv

    def progress_formatter(self) -> LineFormatter:
        return ClaudeJsonlFormatter()

    def apply_output(self, ref: SessionRef, result: CliRunResult) -> None:
        session_id, _text = parse_claude_output(result.stdout)
        if session_id:
            ref.storage["claude_session_id"] = session_id

    def turn_text(self, result: CliRunResult) -> str:
        _session_id, text = parse_claude_output(result.stdout)
        return text


def write_claude_mcp(path: Path, mcp_servers: dict[str, dict[str, Any]]) -> None:
    snippet = write_stdio_mcp_snippet(mcp_servers)
    servers: dict[str, Any] = {}
    for name, spec in snippet.items():
        if not spec.get("command"):
            continue
        entry: dict[str, Any] = {
            "command": spec["command"],
            "args": list(spec.get("args") or []),
        }
        if spec.get("env"):
            entry["env"] = dict(spec["env"])
        entry["timeout"] = mcp_tool_timeout_sec() * 1000
        servers[name] = entry
    if servers:
        path.write_text(
            json.dumps({"mcpServers": servers}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    elif path.exists():
        path.unlink()


def parse_claude_output(stdout: str) -> tuple[str, str]:
    text = (stdout or "").strip()
    if not text:
        return "", ""
    payload = _loads_json_object(text)
    if isinstance(payload, dict):
        session_id, result = _claude_fields(payload)
        if session_id or result:
            return session_id, result or text
    session_id = ""
    result_text = ""
    for raw in text.splitlines():
        event = _loads_json_object(raw.strip())
        if not isinstance(event, dict):
            continue
        found_id, found_text = _claude_fields(event)
        if found_id:
            session_id = found_id
        if str(event.get("type") or "") == "result" and found_text:
            result_text = found_text
    return session_id, result_text or text


def _claude_fields(payload: dict[str, Any]) -> tuple[str, str]:
    session_id = str(payload.get("session_id") or "")
    result = payload.get("result")
    if result is None:
        result = payload.get("text") or ""
    return session_id, str(result).strip()


def _loads_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start or "\n{" in text:
            return None
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None
