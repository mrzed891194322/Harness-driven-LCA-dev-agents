"""Turn archive paths and writers under workspace/memory/logs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .session import SessionConfig, SessionRef


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
    return (
        run_log_dir(workspace_root, run_id)
        / stage_id
        / f"{assignment_id}#{attempt}"
    )


def mcp_render_dir(
    workspace_root: Path,
    run_id: str,
    stage_id: str,
    assignment_id: str,
) -> Path:
    return (
        workspace_root / "tmp" / "mcp-render" / run_id / stage_id / assignment_id
    )


def resolve_mcp_render_dir(config: SessionConfig, storage_dir: Path) -> Path:
    """Prefer SessionConfig.mcp_render_dir; fall back to sdk-sessions storage."""
    target = config.mcp_render_dir or storage_dir
    target.mkdir(parents=True, exist_ok=True)
    return target


def session_config_summary(config: SessionConfig) -> dict[str, Any]:
    """Serialize SessionConfig for archives without dumping process env secrets."""
    mcp_summary: dict[str, Any] = {}
    for name, server in config.mcp_servers.items():
        mcp_summary[name] = {
            "command": server.get("command"),
            "args": list(server.get("args") or []),
            "transport": server.get("transport"),
            "env_keys": sorted(str(key) for key in dict(server.get("env") or {})),
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
    write_json(config.archive_dir / "argv.json", {"argv": list(argv)})


def append_stdout_archive(config: SessionConfig, line: str) -> None:
    if config.archive_dir is None or not line:
        return
    path = config.archive_dir / "stdout.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line if line.endswith("\n") else f"{line}\n")


def finish_turn_archive(config: SessionConfig, ref: SessionRef) -> None:
    archive = config.archive_dir
    if archive is None:
        return
    archive.mkdir(parents=True, exist_ok=True)
    write_json(archive / "session-ref.json", ref.to_dict())
    render = config.mcp_render_dir
    if render is None or not render.is_dir():
        return
    dest = archive / "rendered"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(render, dest)
