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
from harness.tools.control_openlca.utils.workflow import (
    calculate_product_system as run_calculate_product_system,
    get_model_graph as run_get_model_graph,
    import_lci as run_import_lci,
    preflight_import_lci as run_preflight_import_lci,
)


mcp = MCPServer(
    "openLCA-Control",
    instructions=(
        "Query and gated workflow access to the openLCA IPC Server configured "
        "with OPENLCA_IPC_HOST and OPENLCA_IPC_PORT. import_lci is destructive "
        "and requires a matching current preflight hash."
    ),
)

READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

DESTRUCTIVE_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
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


def _workflow_lci_dir(lci_dir: str) -> Path:
    """Limit MCP imports to the workflow-owned LCI directory."""
    configured = Path(lci_dir)
    candidate = configured if configured.is_absolute() else PROJECT_ROOT / configured
    resolved = candidate.resolve()
    allowed = (PROJECT_ROOT / "workspace" / "outputs" / "LCI").resolve()
    if resolved != allowed:
        raise ValueError("lci_dir must resolve exactly to workspace/outputs/LCI")
    return resolved


def _target_category(target_category: str) -> str:
    category = target_category.strip() or PROJECT_ROOT.name
    if any(character in category for character in "\r\n\0"):
        raise ValueError("target_category contains invalid characters")
    return category


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


@mcp.tool(
    description=(
        "Read and validate workspace/outputs/LCI, inspect the active database and target "
        "category, list create/overwrite/delete scope, and return a stable preflight hash. "
        "This tool performs no database writes."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
def preflight_import_lci(
    lci_dir: str = "workspace/outputs/LCI",
    target_category: str = "",
    database_name: str | None = None,
) -> dict[str, Any]:
    """Create a read-only import preflight for the workflow-owned LCI directory."""
    host, port = _endpoint_config()
    return run_preflight_import_lci(
        host=host,
        port=port,
        lci_dir=_workflow_lci_dir(lci_dir),
        target_category=_target_category(target_category),
        database_name=database_name,
    )


@mcp.tool(
    description=(
        "Destructively import workspace/outputs/LCI after rerunning preflight. Requires "
        "an unchanged preflight_hash; otherwise no writes occur."
    ),
    annotations=DESTRUCTIVE_ANNOTATIONS,
    structured_output=True,
)
def import_lci(
    preflight_hash: str,
    lci_dir: str = "workspace/outputs/LCI",
    target_category: str = "",
    database_name: str | None = None,
) -> dict[str, Any]:
    """Import LCI under a precise, current preflight scope."""
    host, port = _endpoint_config()
    return run_import_lci(
        host=host,
        port=port,
        lci_dir=_workflow_lci_dir(lci_dir),
        target_category=_target_category(target_category),
        preflight_hash=preflight_hash,
        database_name=database_name,
    )


@mcp.tool(
    description=(
        "Read a Product System model graph from the active database and report "
        "nodes, edges, broken links, and disconnected nodes."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
def get_model_graph(product_system: str) -> dict[str, Any]:
    """Read and validate an openLCA Product System graph."""
    host, port = _endpoint_config()
    return run_get_model_graph(host, port, product_system)


@mcp.tool(
    description=(
        "Calculate LCIA results for a Product System and Impact Method, returning "
        "category names, UUIDs, amounts, units, settings, and resource-release status."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
def calculate_product_system(
    product_system: str,
    impact_method: str,
    amount: float = 1.0,
    allocation: Literal["physical", "economic", "causal", "none", "default"] | None = None,
    regionalized: bool = False,
    costs: bool = False,
    parameters: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Calculate a Product System and always attempt to release the result handle."""
    host, port = _endpoint_config()
    return run_calculate_product_system(
        host=host,
        port=port,
        product_system=product_system,
        impact_method=impact_method,
        amount=amount,
        allocation=allocation,
        regionalized=regionalized,
        costs=costs,
        parameters=parameters,
    )


if __name__ == "__main__":
    mcp.run()
