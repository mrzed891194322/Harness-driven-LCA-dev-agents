"""MCP local artifact tools; no database or network operations."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Literal

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from mcp.server import MCPServer
from mcp_types import ToolAnnotations

from harness.tools.lca_artifacts import checks, report
from harness.tools.lca_artifacts.store import Context, invoke

mcp = MCPServer(
    "lca-artifacts",
    instructions="Offline checks produce evidence, not stage approval. Artifact paths are relative to workspace.",
)
AUDIT = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)
WRITE = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


@mcp.tool(
    description="Check current-stage inventory, mapping or report; persist an audit without changing reviewed artifacts.",
    annotations=AUDIT,
    structured_output=True,
)
def validate_artifacts(
    profile: Literal["inventory", "mapping", "report"],
) -> dict[str, Any]:
    return invoke(
        "validate_artifacts",
        lambda: checks.validate(Context.environment(), profile),
        arguments={"profile": profile},
    )


@mcp.tool(
    description="Read checks and invalidate changed dependencies; no openLCA calls.",
    annotations=AUDIT,
    structured_output=True,
)
def get_validation_state(
    profile: Literal["inventory", "mapping", "report"],
) -> dict[str, Any]:
    def execute():
        value = checks.validation_state(Context.environment(), profile)
        return {
            "ok": True,
            "checks": [{k: v for k, v in value.items() if k != "inputs"}],
        }

    return invoke("get_validation_state", execute, arguments={"profile": profile})


@mcp.tool(
    description="Determine whether same-run stage-04 retry can reuse raw evidence without any IPC calls.",
    annotations=AUDIT,
    structured_output=True,
)
def get_rework_status() -> dict[str, Any]:
    return invoke(
        "get_rework_status", lambda: checks.reuse_status(Context.environment())
    )


@mcp.tool(
    description="Writer only: replace marked inventory/mapping/LCIA tables while retaining narrative.",
    annotations=WRITE,
    structured_output=True,
)
def render_report_tables() -> dict[str, Any]:
    return invoke("render_report_tables", lambda: report.render(Context.environment()))


@mcp.tool(
    description="Read a bounded UTF-8 slice of a checksummed workspace artifact (offset in characters).",
    annotations=AUDIT,
    structured_output=True,
)
def read_artifact(
    path: str,
    sha256: str,
    offset: int = 0,
    limit: int = 2000,
    json_pointer: str | None = None,
) -> dict[str, Any]:
    def execute():
        if isinstance(offset, bool) or offset < 0 or not 1 <= limit <= 4000:
            raise ValueError("offset >= 0 and limit 1..4000 required")
        ctx = Context.environment()
        text = ctx.resolve_ref({"path": path, "sha256": sha256}).read_text(
            encoding="utf-8"
        )
        if json_pointer is not None:
            if json_pointer and not json_pointer.startswith("/"):
                raise ValueError("json_pointer must be empty or begin with /")
            selected = json.loads(text)
            for token in json_pointer.split("/")[1:] if json_pointer else []:
                key = token.replace("~1", "/").replace("~0", "~")
                selected = (
                    selected[int(key)] if isinstance(selected, list) else selected[key]
                )
            text = json.dumps(selected, ensure_ascii=False, indent=2)
        chunk = text[offset : offset + limit]
        return {
            "ok": True,
            "items": [{"text": chunk}],
            "has_more": offset + len(chunk) < len(text),
            "next_offset": offset + len(chunk)
            if offset + len(chunk) < len(text)
            else None,
        }

    return invoke(
        "read_artifact",
        execute,
        arguments={
            "path": path,
            "offset": offset,
            "limit": limit,
            "json_pointer": json_pointer,
        },
    )


if __name__ == "__main__":
    mcp.run()
