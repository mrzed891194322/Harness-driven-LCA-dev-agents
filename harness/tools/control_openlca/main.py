from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Literal

from mcp.server import MCPServer
from mcp_types import ToolAnnotations


CONTROL_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = CONTROL_ROOT.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.tools.control_openlca.utils.readonly import (
    health_check as run_health_check,
    query_descriptors as run_query_descriptors,
)


mcp = MCPServer(
    "openLCA-Control",
    instructions=(
        "Read-only access to the openLCA IPC Server configured with "
        "OPENLCA_IPC_HOST and OPENLCA_IPC_PORT."
    ),
)

READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)


def _endpoint_config() -> tuple[str, int]:
    host = os.getenv("OPENLCA_IPC_HOST", "127.0.0.1").strip()
    port_text = os.getenv("OPENLCA_IPC_PORT", "8080").strip()
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError("OPENLCA_IPC_PORT must be an integer") from exc
    return host, port


@mcp.tool(
    description="Check whether the configured openLCA IPC Server is reachable and can query the active database.",
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
def health_check() -> dict[str, Any]:
    """Check the configured openLCA IPC Server without modifying data."""
    host, port = _endpoint_config()
    return run_health_check(host, port)


@mcp.tool(
    description="Search descriptors in the active openLCA database and return names, UUIDs, categories, and pagination metadata.",
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
def query_descriptors(
    entity_type: Literal[
        "Process",
        "Flow",
        "ProductSystem",
        "ImpactMethod",
        "FlowProperty",
        "UnitGroup",
        "Actor",
        "Source",
        "Project",
        "Location",
        "Currency",
        "SocialIndicator",
    ],
    search: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Query entity descriptors by a case-insensitive name substring."""
    host, port = _endpoint_config()
    return run_query_descriptors(
        host=host,
        port=port,
        entity_type=entity_type,
        search=search,
        limit=limit,
        offset=offset,
    )


if __name__ == "__main__":
    mcp.run()
