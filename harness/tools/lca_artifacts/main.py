"""Standalone artifact MCP; callers supply files and evidence explicitly."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server import MCPServer
from mcp_types import ToolAnnotations

from harness.tools.control_openlca.utils.workflow import sha256_file
from harness.tools.lca_artifacts import (
    offline_checks as checks,
)
from harness.tools.lca_artifacts import (
    offline_report as report,
)

mcp = MCPServer(
    "lca-artifacts",
    instructions="Offline processing of explicitly supplied files; no workflow context is required.",
)
READ = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, open_world_hint=False
)
WRITE = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, open_world_hint=False
)


@mcp.tool(annotations=READ, structured_output=True)
def validate_inventory(bom_path: str, declared_sources: list[str]) -> dict[str, Any]:
    """Validate inventory rows and their source identifiers."""
    errors = checks.inventory_errors(
        checks.read_items(Path(bom_path)), set(declared_sources)
    )
    return {"ok": not errors, "errors": errors}


@mcp.tool(annotations=READ, structured_output=True)
def validate_mapping(
    bom_path: str,
    mapping_path: str,
    lci_dir: str,
    provider_pairs: list[dict[str, str]],
) -> dict[str, Any]:
    """Validate mapping coverage, LCI structure and explicitly supplied provider pairs."""
    errors = checks.mapping_errors(
        checks.read_items(Path(bom_path)),
        checks.read_items(Path(mapping_path)),
        Path(lci_dir),
        {(pair["process_id"], pair["flow_id"]) for pair in provider_pairs},
    )
    return {"ok": not errors, "errors": errors}


@mcp.tool(annotations=WRITE, structured_output=True)
def render_report_tables(
    report_path: str,
    bom_path: str,
    mapping_path: str,
    calculation_rows: list[list[Any]],
) -> dict[str, Any]:
    """Replace marked tables, preserving narrative. LCIA rows follow the report table columns."""
    return report.render(
        Path(report_path),
        checks.read_items(Path(bom_path)),
        checks.read_items(Path(mapping_path)),
        calculation_rows,
    )


@mcp.tool(annotations=READ, structured_output=True)
def read_artifact(
    path: str,
    sha256: str,
    offset: int = 0,
    limit: int = 2000,
    json_pointer: str | None = None,
) -> dict[str, Any]:
    """Read a checksummed UTF-8 file; offset and limit count characters."""
    if isinstance(offset, bool) or offset < 0 or not 1 <= limit <= 4000:
        raise ValueError("offset >= 0 and limit 1..4000 required")
    source = Path(path)
    if sha256_file(source) != sha256:
        raise ValueError("artifact checksum mismatch")
    text = source.read_text(encoding="utf-8")
    if json_pointer is not None:
        if json_pointer and not json_pointer.startswith("/"):
            raise ValueError("json_pointer must be empty or begin with /")
        value = json.loads(text)
        for token in json_pointer.split("/")[1:] if json_pointer else []:
            key = token.replace("~1", "/").replace("~0", "~")
            value = value[int(key)] if isinstance(value, list) else value[key]
        text = json.dumps(value, ensure_ascii=False, indent=2)
    chunk = text[offset : offset + limit]
    has_more = offset + len(chunk) < len(text)
    return {
        "ok": True,
        "items": [{"text": chunk}],
        "has_more": has_more,
        "next_offset": offset + len(chunk) if has_more else None,
    }


if __name__ == "__main__":
    mcp.run()
