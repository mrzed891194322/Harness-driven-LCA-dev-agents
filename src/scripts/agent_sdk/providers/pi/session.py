from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...archive import resolve_mcp_render_dir
from ...catalog import split_pi_model_ref
from ...permissions import pi_tools_flag
from ...progress import LineFormatter
from ...session import SessionConfig, SessionRef, SessionResumeError
from ..cli_base import CliRunResult, CliSessionProvider
from ..store import write_stdio_mcp_snippet
from .jsonl import PiJsonlFormatter


class PiSessionProvider(CliSessionProvider):
    worker = "pi"
    binary = "pi"

    def resume(self, ref: SessionRef, config: SessionConfig) -> SessionRef:
        saved = super().resume(ref, config)
        if not Path(saved.storage.get("dir", "")).is_dir():
            raise SessionResumeError("Pi 会话存储目录不存在")
        return saved

    def _assert_native_storage(self, ref: SessionRef, config: SessionConfig) -> None:
        del config
        if not Path(ref.storage.get("dir", "")).is_dir():
            raise SessionResumeError("Pi 会话存储目录不存在")

    def _create_storage(
        self,
        config: SessionConfig,
        storage_dir: Path,
        session_id: str,
    ) -> dict[str, str]:
        del session_id
        mcp_path = resolve_mcp_render_dir(config, storage_dir) / "mcp.json"
        write_pi_mcp(mcp_path, config.mcp_servers)
        return {
            "mcp_path": str(mcp_path) if config.mcp_servers else "",
            "session_dir": str(storage_dir),
        }

    def _prepare_turn(self, ref: SessionRef, config: SessionConfig) -> None:
        render_dir = resolve_mcp_render_dir(config, Path(ref.storage["dir"]))
        mcp_path = render_dir / "mcp.json"
        write_pi_mcp(mcp_path, config.mcp_servers)
        ref.storage["mcp_path"] = str(mcp_path) if config.mcp_servers else ""
        ref.storage["session_dir"] = str(Path(ref.storage["dir"]))

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
            "--mode",
            "json",
            "-a",
            "--tools",
            pi_tools_flag(),
        ]
        if config.model:
            provider, model_id = split_pi_model_ref(config.model)
            if provider:
                argv.extend(["--provider", provider])
            if model_id:
                argv.extend(["--model", model_id])
        session_path = ref.storage.get("session_path") or ""
        if session_path:
            argv.extend(["--session", session_path])
        else:
            session_dir = ref.storage.get("session_dir") or ref.storage.get("dir") or ""
            if session_dir:
                argv.extend(["--session-dir", session_dir])
        mcp_path = ref.storage.get("mcp_path") or ""
        if mcp_path:
            argv.extend(["-e", "npm:pi-mcp-adapter", "--mcp-config", mcp_path])
        return argv

    def progress_formatter(self) -> LineFormatter:
        return PiJsonlFormatter()

    def apply_output(self, ref: SessionRef, result: CliRunResult) -> None:
        session_id, _text = parse_pi_output(result.stdout)
        if session_id:
            ref.storage["pi_session_id"] = session_id
        session_path = _latest_session_file(Path(ref.storage.get("dir") or ""))
        if session_path:
            ref.storage["session_path"] = session_path

    def turn_text(self, result: CliRunResult) -> str:
        _session_id, text = parse_pi_output(result.stdout)
        return text


def write_pi_mcp(path: Path, mcp_servers: dict[str, dict[str, Any]]) -> None:
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
        entry["timeout"] = spec["tool_timeout_sec"] * 1000
        servers[name] = entry
    if servers:
        path.write_text(
            json.dumps({"mcpServers": servers}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    elif path.exists():
        path.unlink()


def parse_pi_output(stdout: str) -> tuple[str, str]:
    session_id = ""
    texts: list[str] = []
    for raw in (stdout or "").splitlines():
        line = raw.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        event_type = str(payload.get("type") or "")
        found_id = payload.get("id") or payload.get("session_id")
        if event_type == "session" and found_id:
            session_id = str(found_id)
        elif found_id and not session_id:
            session_id = str(found_id)
        text = _pi_event_text(payload)
        if text:
            texts.append(text)
    joined = "\n".join(texts).strip()
    return session_id, joined or (stdout or "").strip()


def _pi_event_text(payload: dict[str, Any]) -> str:
    event_type = str(payload.get("type") or "")
    if event_type in {"message_end", "turn_end", "agent_end"}:
        message = payload.get("message")
        extracted = _message_text(message)
        if extracted:
            return extracted
        if event_type == "agent_end":
            for item in payload.get("messages") or []:
                extracted = _message_text(item)
                if extracted:
                    return extracted
    result = payload.get("result") or payload.get("text")
    if result:
        return str(result).strip()
    return ""


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


def _latest_session_file(storage_dir: Path) -> str:
    if not storage_dir.is_dir():
        return ""
    files = sorted(path for path in storage_dir.glob("*.jsonl") if path.is_file())
    if not files:
        return ""
    return str(files[-1])
