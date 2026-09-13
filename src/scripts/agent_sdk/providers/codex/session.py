from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...openlca_mcp_timeout import mcp_tool_timeout_sec
from ...permissions import CODEX_SANDBOX
from ...progress import LineFormatter
from ...session import SessionConfig, SessionRef, SessionResumeError
from ..cli_base import CliRunResult, CliSessionProvider
from ..store import write_stdio_mcp_snippet
from .jsonl import CodexJsonlFormatter


class CodexSessionProvider(CliSessionProvider):
    worker = "codex"
    binary = "codex"

    def resume(self, ref: SessionRef, config: SessionConfig) -> SessionRef:
        saved = super().resume(ref, config)
        if not Path(saved.storage.get("dir", "")).is_dir():
            raise SessionResumeError("Codex 会话存储目录不存在")
        return saved

    def _assert_native_storage(self, ref: SessionRef, config: SessionConfig) -> None:
        del config
        if not Path(ref.storage.get("dir", "")).is_dir():
            raise SessionResumeError("Codex 会话存储目录不存在")

    def build_command(
        self,
        binary: str,
        ref: SessionRef,
        prompt: str,
        config: SessionConfig,
    ) -> list[str]:
        argv = [binary, "exec", "--json", "--color", "never", "-s", CODEX_SANDBOX]
        if config.model:
            argv.extend(["-m", config.model])
        for row in mcp_overrides(config.mcp_servers):
            argv.extend(["-c", row])
        thread_id = ref.storage.get("thread_id") or ""
        if thread_id:
            argv.extend(["resume", thread_id])
        argv.append(prompt)
        return argv

    def progress_formatter(self) -> LineFormatter:
        return CodexJsonlFormatter(key_only=True)

    def apply_output(self, ref: SessionRef, result: CliRunResult) -> None:
        thread_id, _text = parse_codex_output(result.stdout)
        if thread_id:
            ref.storage["thread_id"] = thread_id

    def turn_text(self, result: CliRunResult) -> str:
        _thread_id, text = parse_codex_output(result.stdout)
        return text


def mcp_overrides(mcp_servers: dict[str, dict[str, Any]]) -> tuple[str, ...]:
    snippet = write_stdio_mcp_snippet(mcp_servers)
    rows: list[str] = []
    for name, spec in snippet.items():
        rows.append(f"mcp_servers.{name}.tool_timeout_sec={mcp_tool_timeout_sec()}")
        rows.append(f"mcp_servers.{name}.startup_timeout_sec=30")
        if spec.get("command"):
            rows.append(f"mcp_servers.{name}.command={spec['command']}")
        args = spec.get("args") or []
        if args:
            rendered = ", ".join(json.dumps(item) for item in args)
            rows.append(f"mcp_servers.{name}.args=[{rendered}]")
        for key, value in spec.get("env", {}).items():
            rows.append(f"mcp_servers.{name}.env.{json.dumps(key)}={json.dumps(value)}")
    return tuple(rows)


def parse_codex_output(stdout: str) -> tuple[str, str]:
    thread_id = ""
    texts: list[str] = []
    for raw in (stdout or "").splitlines():
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        found = _find_str(payload, ("thread_id", "session_id"))
        if found:
            thread_id = found
        item = payload.get("item") if isinstance(payload, dict) else None
        if isinstance(item, dict) and item.get("type") == "agent_message":
            text = item.get("text")
            if text:
                texts.append(str(text))
    return thread_id, "\n".join(texts).strip() or (stdout or "").strip()


def _find_str(payload: Any, keys: tuple[str, ...]) -> str:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if value:
                return str(value)
        for value in payload.values():
            found = _find_str(value, keys)
            if found:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _find_str(item, keys)
            if found:
                return found
    return ""


_mcp_overrides = mcp_overrides
