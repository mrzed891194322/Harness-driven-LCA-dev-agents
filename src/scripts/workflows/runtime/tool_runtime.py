"""Declarative MCP tool run-context binding."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .context import RunContext

CONTEXT_FILE_FLAG_DEFAULT = "--context-file"
DEFAULT_ENV_PREFIX = "HARNESS"


@dataclass(frozen=True)
class ToolRuntimeSpec:
    run_context_env: bool = False
    context_file: bool = False
    context_file_flag: str = CONTEXT_FILE_FLAG_DEFAULT
    env_prefix: str | None = None


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def mcp_context_path(
    workspace_root: Path, run_id: str, stage_id: str, assignment_id: str
) -> Path:
    return (
        workspace_root
        / "tmp"
        / "mcp-context"
        / run_id
        / stage_id
        / f"{assignment_id}.json"
    )


def write_context_file(ctx: RunContext) -> Path:
    path = mcp_context_path(
        ctx.workspace_root, ctx.run_id, ctx.stage_id, ctx.assignment_id
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        path,
        {
            "run_id": ctx.run_id,
            "stage": ctx.stage_id,
            "attempt": ctx.attempt,
            "role": ctx.role,
            "assignment": ctx.assignment_id,
            "workspace": str(ctx.workspace_root),
            "metadata": dict(ctx.metadata),
        },
    )
    return path.resolve()


def run_context_env(ctx: RunContext, spec: ToolRuntimeSpec) -> dict[str, str]:
    prefix = spec.env_prefix or DEFAULT_ENV_PREFIX
    return {
        f"{prefix}_RUN_ID": ctx.run_id,
        f"{prefix}_STAGE": ctx.stage_id,
        f"{prefix}_ATTEMPT": str(ctx.attempt),
        f"{prefix}_ROLE": ctx.role,
        f"{prefix}_WORKSPACE": str(ctx.workspace_root),
        f"{prefix}_ASSIGNMENT": ctx.assignment_id,
        f"{prefix}_METADATA_JSON": json.dumps(ctx.metadata, ensure_ascii=False),
    }


def with_context_file(args: list[str], path: Path, flag: str) -> list[str]:
    rendered = list(args)
    if flag in rendered:
        index = rendered.index(flag)
        if index + 1 < len(rendered) and not str(rendered[index + 1]).startswith("-"):
            rendered[index + 1] = str(path)
            return rendered
        rendered.insert(index + 1, str(path))
        return rendered
    return rendered + [flag, str(path)]


def apply_tool_runtime(
    server: dict[str, Any],
    runtime: ToolRuntimeSpec | None,
    ctx: RunContext,
    *,
    uv_cache_dir: str,
    context_path: Path | None,
) -> None:
    merged: dict[str, Any] = {**server.get("env", {}), "UV_CACHE_DIR": uv_cache_dir}
    if runtime and runtime.run_context_env:
        merged.update(run_context_env(ctx, runtime))
    if runtime and runtime.context_file and context_path is not None:
        server["args"] = with_context_file(
            list(server.get("args") or []),
            context_path,
            runtime.context_file_flag,
        )
    server["env"] = merged
