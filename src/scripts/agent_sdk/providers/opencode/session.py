from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...archive import resolve_mcp_render_dir
from ...openlca_mcp_timeout import mcp_tool_timeout_sec
from ...permissions import opencode_permission_config
from ...progress import LineFormatter
from ...session import SessionConfig, SessionRef, SessionResumeError
from ..cli_base import CliRunResult, CliSessionProvider
from ..store import write_stdio_mcp_snippet
from .jsonl import OpenCodeJsonlFormatter


def _mcp_timeout_ms() -> int:
    return mcp_tool_timeout_sec() * 1000


class OpenCodeSessionProvider(CliSessionProvider):
    worker = "opencode"
    binary = "opencode"
    _config_path = ""

    def resume(self, ref: SessionRef, config: SessionConfig) -> SessionRef:
        saved = super().resume(ref, config)
        if not Path(saved.storage.get("dir", "")).is_dir():
            raise SessionResumeError("OpenCode 会话存储目录不存在")
        return saved

    def _assert_native_storage(self, ref: SessionRef, config: SessionConfig) -> None:
        del config
        if not Path(ref.storage.get("dir", "")).is_dir():
            raise SessionResumeError("OpenCode 会话存储目录不存在")

    def _create_storage(
        self,
        config: SessionConfig,
        storage_dir: Path,
        session_id: str,
    ) -> dict[str, str]:
        del session_id
        render_dir = resolve_mcp_render_dir(config, storage_dir)
        config_path = write_opencode_config(render_dir / "opencode.json", config)
        self._config_path = config_path
        return {"config_path": config_path}

    def _prepare_turn(self, ref: SessionRef, config: SessionConfig) -> None:
        render_dir = resolve_mcp_render_dir(config, Path(ref.storage["dir"]))
        config_path = write_opencode_config(render_dir / "opencode.json", config)
        ref.storage["config_path"] = config_path
        self._config_path = config_path

    def build_command(
        self,
        binary: str,
        ref: SessionRef,
        prompt: str,
        config: SessionConfig,
    ) -> list[str]:
        argv = [binary, "run", "--format", "json"]
        if config.model:
            argv.extend(["-m", config.model])
        native = ref.storage.get("opencode_session_id") or ""
        if native:
            argv.extend(["-s", native])
        argv.append(prompt)
        return argv

    def progress_formatter(self) -> LineFormatter:
        return OpenCodeJsonlFormatter()

    def build_env(self, config: SessionConfig) -> dict[str, str]:
        env = super().build_env(config)
        if self._config_path:
            env["OPENCODE_CONFIG"] = self._config_path
        return env

    def apply_output(self, ref: SessionRef, result: CliRunResult) -> None:
        session_id, _text = parse_opencode_output(result.stdout)
        if session_id:
            ref.storage["opencode_session_id"] = session_id

    def turn_text(self, result: CliRunResult) -> str:
        _session_id, text = parse_opencode_output(result.stdout)
        return text


def write_opencode_config(path: Path, config: SessionConfig) -> str:
    payload = opencode_config_payload(config.mcp_servers)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(path)


def opencode_config_payload(
    mcp_servers: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "permission": opencode_permission_config(mcp_servers),
    }
    servers = write_opencode_mcp(mcp_servers)
    if servers:
        payload["mcp"] = servers
    return payload


def write_opencode_mcp(
    mcp_servers: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    snippet = write_stdio_mcp_snippet(mcp_servers)
    servers: dict[str, Any] = {}
    for name, spec in snippet.items():
        command = spec.get("command")
        if not command:
            continue
        argv = [str(command), *[str(item) for item in spec.get("args") or []]]
        entry: dict[str, Any] = {
            "type": "local",
            "command": argv,
            "enabled": True,
            "timeout": _mcp_timeout_ms(),
        }
        if spec.get("env"):
            entry["environment"] = dict(spec["env"])
        servers[name] = entry
    return servers


def parse_opencode_output(stdout: str) -> tuple[str, str]:
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
        found_id = payload.get("sessionID") or payload.get("session_id")
        if found_id and not session_id:
            session_id = str(found_id)
        text = _opencode_event_text(payload)
        if text:
            texts.append(text)
    joined = "\n".join(texts).strip()
    return session_id, joined or (stdout or "").strip()


def _opencode_event_text(payload: dict[str, Any]) -> str:
    if str(payload.get("type") or "") != "text":
        return ""
    part = payload.get("part")
    if isinstance(part, dict):
        text = part.get("text")
        if text:
            return str(text).strip()
    text = payload.get("text")
    return str(text).strip() if text else ""
