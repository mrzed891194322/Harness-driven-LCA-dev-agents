"""Turn archive paths and writers under workspace/memory/logs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.runtime.hashing import sha256_file

from .session import SessionConfig, SessionRef

REDACTED = "<redacted>"


def run_log_dir(workspace_root: Path, run_id: str) -> Path:
    return workspace_root / "memory" / "logs" / run_id


def progress_log_path(workspace_root: Path, run_id: str) -> Path:
    return run_log_dir(workspace_root, run_id) / "progress.txt"


def turn_archive_dir(
    workspace_root: Path,
    run_id: str,
    stage_id: str,
    assignment_id: str,
    attempt: int,
) -> Path:
    return run_log_dir(workspace_root, run_id) / stage_id / f"{assignment_id}#{attempt}"


def mcp_render_dir(
    workspace_root: Path,
    run_id: str,
    stage_id: str,
    assignment_id: str,
) -> Path:
    return workspace_root / "tmp" / "mcp-render" / run_id / stage_id / assignment_id


def resolve_mcp_render_dir(config: SessionConfig, storage_dir: Path) -> Path:
    """Prefer SessionConfig.mcp_render_dir; fall back to sdk-sessions storage."""
    target = config.mcp_render_dir or storage_dir
    target.mkdir(parents=True, exist_ok=True)
    return target


def _mcp_secret_values(config: SessionConfig) -> list[str]:
    secrets: list[str] = []
    for server in config.mcp_servers.values():
        for value in dict(server.get("env") or {}).values():
            text = str(value)
            if text:
                secrets.append(text)
        for value in dict(server.get("headers") or {}).values():
            text = str(value)
            if text:
                secrets.append(text)
    # Longest first so overlapping replacements stay stable.
    return sorted(set(secrets), key=len, reverse=True)


def redact_secrets(text: str, secrets: list[str]) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, REDACTED)
    return redacted


def session_config_summary(config: SessionConfig) -> dict[str, Any]:
    """Serialize SessionConfig for archives without dumping MCP secret values."""
    mcp_summary: dict[str, Any] = {}
    for name, server in config.mcp_servers.items():
        mcp_summary[name] = {
            "command": server.get("command"),
            "args": list(server.get("args") or []),
            "transport": server.get("transport"),
            "env_keys": sorted(str(key) for key in dict(server.get("env") or {})),
            "header_keys": sorted(
                str(key) for key in dict(server.get("headers") or {})
            ),
        }
    return {
        "worker": config.worker,
        "cwd": str(config.cwd),
        "tmp_dir": str(config.tmp_dir),
        "model": config.model,
        "spec_paths": list(config.spec_paths),
        "rule_ids": list(config.rule_ids),
        "tool_ids": list(config.tool_ids),
        "stage_id": config.stage_id,
        "role": config.role,
        "attempt": config.attempt,
        "run_id": config.run_id,
        "mcp_render_dir": str(config.mcp_render_dir) if config.mcp_render_dir else "",
        "archive_dir": str(config.archive_dir) if config.archive_dir else "",
        "mcp_servers": mcp_summary,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def begin_turn_archive(config: SessionConfig, prompt: str) -> Path | None:
    archive = config.archive_dir
    if archive is None:
        return None
    archive.mkdir(parents=True, exist_ok=True)
    write_json(archive / "session-config.json", session_config_summary(config))
    (archive / "prompt.md").write_text(prompt, encoding="utf-8")
    return archive


def write_argv_archive(config: SessionConfig, argv: list[str]) -> None:
    if config.archive_dir is None:
        return
    secrets = _mcp_secret_values(config)
    redacted_argv = [redact_secrets(str(item), secrets) for item in argv]
    write_json(config.archive_dir / "argv.json", {"argv": redacted_argv})


def append_stdout_archive(config: SessionConfig, line: str) -> None:
    if config.archive_dir is None or not line:
        return
    path = config.archive_dir / "stdout.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line if line.endswith("\n") else f"{line}\n")


def _rendered_manifest(render: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(render.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(render)).replace("\\", "/")
        files.append(
            {
                "path": rel,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "source_dir": str(render),
        "files": files,
        "note": "MCP render content retained only under workspace/tmp/mcp-render; "
        "persistent logs store metadata only",
    }


def finish_turn_archive(config: SessionConfig, ref: SessionRef) -> None:
    archive = config.archive_dir
    if archive is None:
        return
    archive.mkdir(parents=True, exist_ok=True)
    write_json(archive / "session-ref.json", ref.to_dict())
    render = config.mcp_render_dir
    if render is None or not render.is_dir():
        return
    # Do not copy rendered MCP configs (may contain secrets) into persistent logs.
    write_json(archive / "rendered-manifest.json", _rendered_manifest(render))
