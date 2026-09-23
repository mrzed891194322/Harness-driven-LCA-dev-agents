"""Standalone one-shot worker run (not used by the orchestrated workflow)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .session import SessionConfig, default_client


def run(
    prompt: str,
    worker: str,
    *,
    cwd: Path | None = None,
    tmp_dir: Path | None = None,
    mcp_servers: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Create a throwaway session, send one prompt, release the connection."""
    root = cwd or Path.cwd()
    config = SessionConfig(
        worker=worker,
        cwd=root,
        tmp_dir=tmp_dir or (root / "workspace" / "tmp"),
        mcp_servers=mcp_servers or {},
    )
    client = default_client()
    ref = client.create(config)
    try:
        result = client.run_turn(ref, prompt, config)
        return result.text
    finally:
        client.release(ref)
