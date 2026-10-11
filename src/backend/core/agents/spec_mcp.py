"""Bind the spec_mcp child for one Pi session (P5 spec channels).

Core reads the launch manifest ``harness/tools/mcp/spec_mcp/mcp.yaml`` and binds
run_id / stage / role / attempt into the child's environment, signed with an
HMAC key kept under ``.local/run/`` (outside every agent read scope). The agent
cannot pass or change any of these: spec_mcp tools take no stage arguments and
refuse to run if the signature does not match.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

import yaml

from backend.core.agents.mcp import rewrite_uv_run_python, validate_stdio_server

SERVER_NAME = "spec_mcp"
MANIFEST = Path("harness") / "tools" / "mcp" / "spec_mcp" / "mcp.yaml"
KEY_FILE = Path(".local") / "run" / "spec_mcp.key"
BINDING_ENV = "SPEC_MCP_BINDING"
TOKEN_ENV = "SPEC_MCP_TOKEN"
KEY_FILE_ENV = "SPEC_MCP_KEY_FILE"


def canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sign(key: bytes, payload: dict[str, Any]) -> str:
    return hmac.new(key, canonical(payload).encode("utf-8"), hashlib.sha256).hexdigest()


def ensure_key(project_root: Path) -> Path:
    path = project_root / KEY_FILE
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, os.urandom(32).hex().encode())
        finally:
            os.close(fd)
    return path.resolve()


def load_manifest(project_root: Path) -> dict[str, Any]:
    path = project_root / MANIFEST
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{MANIFEST}: must be a mapping")
    entry = {
        "transport": raw.get("transport", "stdio"),
        "command": raw.get("command"),
        "args": [str(a) for a in raw.get("args") or []],
        "tool_timeout_sec": int(raw.get("tool_timeout_sec", 300)),
    }
    validate_stdio_server(SERVER_NAME, entry)
    return entry


def spec_mcp_server(
    *,
    project_root: Path,
    workspace_root: Path,
    run_id: str,
    stage_id: str,
    role: str,
    attempt: int,
    assignment_id: str,
    spec_relative: str,
    handoff_relative: str,
    metadata: dict[str, Any] | None = None,
    uv_cache_dir: str | None = None,
) -> dict[str, Any]:
    """Session MCP server entry (``mcp_servers`` shape) for spec_mcp."""
    entry = rewrite_uv_run_python({**load_manifest(project_root), "name": SERVER_NAME})
    spec_rel = spec_relative.replace("\\", "/")
    if spec_rel.startswith("harness/"):
        spec_rel = spec_rel[len("harness/") :]
    binding = {
        "run_id": run_id,
        "stage": stage_id,
        "role": role,
        "attempt": int(attempt),
        "assignment": assignment_id,
        "project_root": str(project_root.resolve()),
        "workspace": str(workspace_root.resolve()),
        "spec": spec_rel,
        "handoff_path": handoff_relative,
        "metadata": dict(metadata or {}),
    }
    key_path = ensure_key(project_root)
    env = {
        BINDING_ENV: canonical(binding),
        TOKEN_ENV: sign(key_path.read_bytes(), binding),
        KEY_FILE_ENV: str(key_path),
    }
    if uv_cache_dir:
        env["UV_CACHE_DIR"] = uv_cache_dir
    entry["env"] = env
    return entry
