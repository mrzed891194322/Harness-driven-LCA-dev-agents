from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Literal

from mcp.server import MCPServer
from mcp_types import ToolAnnotations


CONTROL_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = CONTROL_ROOT.parents[2]
IMPORT_OPERATION_DIR = PROJECT_ROOT / "workspace" / "memory" / "import-operations"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.tools.control_openlca.utils.readonly import (
    get_flow_providers as run_get_flow_providers,
    get_process_details as run_get_process_details,
    health_check as run_health_check,
    query_descriptors as run_query_descriptors,
)
from harness.tools.control_openlca.utils.workflow import (
    calculate_product_system as run_calculate_product_system,
    get_import_operation as run_get_import_operation,
    get_model_graph as run_get_model_graph,
    import_lci as run_import_lci,
    preflight_import_lci as run_preflight_import_lci,
)


mcp = MCPServer(
    "openLCA-Control",
    instructions=(
        "Query and gated workflow access to the openLCA IPC Server configured "
        "with OPENLCA_IPC_HOST and OPENLCA_IPC_PORT. import_lci is destructive "
        "and requires a matching current import scope."
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
    """Limit MCP imports to canonical LCI or a workflow compatibility directory."""
    project_root = PROJECT_ROOT.resolve()
    configured = Path(lci_dir)
    candidate = configured if configured.is_absolute() else project_root / configured
    resolved = candidate.resolve()
    canonical = project_root / "workspace" / "outputs" / "LCI"
    temporary_root = project_root / "workspace" / "tmp"
    if resolved != canonical and temporary_root not in resolved.parents:
        raise ValueError(
            "lci_dir must resolve to workspace/outputs/LCI or a subdirectory "
            "of workspace/tmp"
        )
    return resolved


def _target_category(target_category: str) -> str:
    category = target_category.strip() or PROJECT_ROOT.name
    if any(character in category for character in "\r\n\0"):
        raise ValueError("target_category contains invalid characters")
    return category


@mcp.tool(
    description=(
        "Check whether the configured openLCA IPC Server and active database "
        "respond, retrying with three fresh clients after the first failed probe."
    ),
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
        "Read one exact openLCA Process UUID and return compact process metadata, "
        "location, and quantitative-reference exchanges."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
def get_process_details(process_id: str) -> dict[str, Any]:
    """Read compact details for one exact Process UUID."""
    host, port = _endpoint_config()
    return run_get_process_details(host, port, process_id)


@mcp.tool(
    description=(
        "List the exact openLCA Process providers for one Flow UUID, with compact "
        "provider UUID, name, category, location, flow reference, and pagination."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
def get_flow_providers(
    flow_id: str,
    location: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Query provider candidates for one exact Flow UUID."""
    host, port = _endpoint_config()
    return run_get_flow_providers(
        host=host,
        port=port,
        flow_id=flow_id,
        location=location,
        limit=limit,
        offset=offset,
    )


@mcp.tool(
    description=(
        "Read and validate canonical workspace/outputs/LCI or a compatibility LCI under "
        "workspace/tmp, inspect the active database and target category, and list "
        "create/overwrite/delete scope. This tool performs no database writes."
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
        operation_dir=IMPORT_OPERATION_DIR,
    )


@mcp.tool(
    description=(
        "Destructively import canonical workspace/outputs/LCI or a compatibility LCI "
        "under workspace/tmp after rerunning preflight. Rejects the write when the "
        "database name, target category, or LCI directory does not match the last "
        "successful preflight scope."
    ),
    annotations=DESTRUCTIVE_ANNOTATIONS,
    structured_output=True,
)
def import_lci(
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
        database_name=database_name,
        operation_dir=IMPORT_OPERATION_DIR,
    )


@mcp.tool(
    description=(
        "Read the persisted import journal. Use this after a timeout before deciding "
        "whether another destructive call is safe."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
def get_import_operation() -> dict[str, Any]:
    """Read an import journal without writing to openLCA."""
    return run_get_import_operation(IMPORT_OPERATION_DIR)


@mcp.tool(
    description=(
        "Read a Product System model graph from the active database and report "
        "nodes, edges, broken links, and disconnected nodes."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
def get_model_graph(
    product_system: str,
    expected_process_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Read and validate an openLCA Product System graph."""
    host, port = _endpoint_config()
    return run_get_model_graph(
        host,
        port,
        product_system,
        expected_process_ids=expected_process_ids,
    )


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
