# ruff: noqa: E402
"""Standalone openLCA MCP. Inputs and journal location are supplied explicitly."""

from __future__ import annotations

import functools
import inspect
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from mcp.server import MCPServer
from mcp_types import ToolAnnotations

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from harness.tools.shared.control_openlca import operations, readonly
from harness.tools.shared.control_openlca.cleanup import run_cleanup_output
from harness.tools.shared.control_openlca.connection import (
    ipc_budget_scope,
    ipc_tool_is_long_running,
    ipc_tool_profile,
    resolve_ipc_tool_timeout_sec,
)
from harness.tools.shared.control_openlca.guard import serialized_ipc
from harness.tools.shared.control_openlca.readonly import (
    get_flow_providers as run_get_flow_providers,
)
from harness.tools.shared.control_openlca.readonly import (
    get_process_details as run_get_process_details,
)
from harness.tools.shared.control_openlca.readonly import (
    health_check as run_health_check,
)
from harness.tools.shared.control_openlca.readonly import (
    query_descriptors as run_query_descriptors,
)
from harness.tools.shared.control_openlca.workflow import (
    calculate_product_system as run_calculate_product_system,
)
from harness.tools.shared.control_openlca.workflow import (
    get_model_graph as run_get_model_graph,
)


def ipc_tool(name):
    """Apply only IPC serialization and time budgets; no workflow policy."""

    def decorate(function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            bound = inspect.signature(function).bind(*args, **kwargs)
            bound.apply_defaults()
            params = dict(bound.arguments)
            timeout = params.pop("timeout_sec", None)
            profile = ipc_tool_profile(name)
            if profile == "none":
                return function(**params)
            host, port = _endpoint_config()
            runner: Callable[..., Any] = serialized_ipc(
                lambda host, port: function(**params),
                long_running=ipc_tool_is_long_running(name),
            )
            if profile == "long":
                budget = resolve_ipc_tool_timeout_sec(timeout)
                with ipc_budget_scope(budget):
                    result = runner(host, port)
                result["applied_timeout_sec"] = int(budget)
                return result
            return runner(host, port)

        return wrapped

    return decorate


mcp = MCPServer(
    "openLCA-Control",
    instructions=(
        "Independent access to the openLCA IPC Server configured "
        "with OPENLCA_IPC_HOST and OPENLCA_IPC_PORT. import_lci and cleanup_output "
        "are destructive; import_lci requires a matching current import scope. "
        "Long-running tools accept optional timeout_sec (300-7200) for IPC session "
        "budget and per-request HTTP reads; do not wrap tools in shell timeout."
    ),
)

READ_ONLY_ANNOTATIONS = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)

DESTRUCTIVE_ANNOTATIONS = ToolAnnotations(
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=False,
    open_world_hint=True,
)


def _endpoint_config() -> tuple[str, int]:
    host = os.getenv("OPENLCA_IPC_HOST", "127.0.0.1").strip()
    port_text = os.getenv("OPENLCA_IPC_PORT", "8080").strip()
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError("OPENLCA_IPC_PORT must be an integer") from exc
    return host, port


def _target_category(target_category: str) -> str:
    category = target_category.strip()
    if not category or any(character in category for character in "\r\n\0"):
        raise ValueError(
            "target_category must be nonempty and contain no control characters"
        )
    return category


@mcp.tool(
    description=(
        "Check whether the configured openLCA IPC Server and active database "
        "respond, retrying with three fresh clients after the first failed probe."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
@ipc_tool("health_check")
def health_check() -> dict[str, Any]:
    """Check the configured openLCA IPC Server without modifying data."""
    host, port = _endpoint_config()
    return run_health_check(host, port)


@mcp.tool(
    description=(
        "Search descriptors in the active openLCA database and return names, UUIDs, "
        "categories, and pagination metadata. Optional timeout_sec (300-7200) sets "
        "the IPC session budget for large databases."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
@ipc_tool("query_descriptors")
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
    timeout_sec: int | None = None,
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
        "location, and quantitative-reference exchanges. Optional timeout_sec "
        "(300-7200) sets the IPC session budget."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
@ipc_tool("get_process_details")
def get_process_details(
    process_id: str,
    timeout_sec: int | None = None,
) -> dict[str, Any]:
    """Read compact details for one exact Process UUID."""
    host, port = _endpoint_config()
    return run_get_process_details(host, port, process_id)


@mcp.tool(
    description=(
        "List the exact openLCA Process providers for one Flow UUID, with compact "
        "provider UUID, name, category, location, flow reference, and pagination. "
        "Optional timeout_sec (300-7200) sets the IPC session budget."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
@ipc_tool("get_flow_providers")
def get_flow_providers(
    flow_id: str,
    location: str = "",
    limit: int = 50,
    offset: int = 0,
    timeout_sec: int | None = None,
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
        "Read and validate the supplied LCI directory, "
        "inspect the active database and target category, and list "
        "create/overwrite/delete scope. This tool performs no database writes. "
        "Optional timeout_sec (300-7200) sets the IPC session budget for slow databases."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
@ipc_tool("preflight_import_lci")
def preflight_import_lci(
    lci_dir: str,
    target_category: str,
    operation_dir: str,
    scope_id: str,
    database_name: str | None = None,
    timeout_sec: int | None = None,
) -> dict[str, Any]:
    """Inspect an LCI directory and save a preflight in the supplied journal."""
    host, port = _endpoint_config()
    return operations.preflight(
        host=host,
        port=port,
        lci_dir=Path(lci_dir),
        target_category=_target_category(target_category),
        database_name=database_name,
        operation_dir=Path(operation_dir),
        run_id=scope_id,
    )


@mcp.tool(
    description=(
        "Import the supplied LCI directory "
        "after rerunning preflight. Rejects the write when the "
        "database name, target category, or LCI directory does not match the last "
        "successful preflight scope. Optional timeout_sec (300-7200) extends the IPC "
        "session budget; do not wrap this tool in shell timeout."
    ),
    annotations=DESTRUCTIVE_ANNOTATIONS,
    structured_output=True,
)
@ipc_tool("import_lci")
def import_lci(
    request_id: str,
    preflight_id: str,
    lci_dir: str,
    target_category: str,
    operation_dir: str,
    scope_id: str,
    database_name: str | None = None,
    timeout_sec: int | None = None,
) -> dict[str, Any]:
    """Import only after a matching fresh preflight; persist request identity."""
    host, port = _endpoint_config()
    return operations.import_request(
        host=host,
        port=port,
        lci_dir=Path(lci_dir),
        target_category=_target_category(target_category),
        database_name=database_name,
        operation_dir=Path(operation_dir),
        run_id=scope_id,
        request_id=request_id,
        preflight_id=preflight_id,
    )


@mcp.tool(
    description=(
        "Read the persisted import journal. Use this after a timeout before deciding "
        "whether another destructive call is safe."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
@ipc_tool("get_import_operation")
def get_import_operation(
    operation_dir: str,
    scope_id: str,
    request_id: str | None = None,
    operation_id: str | None = None,
) -> dict[str, Any]:
    """Read a journal without database writes."""
    return operations.get_operation(
        Path(operation_dir),
        run_id=scope_id,
        request_id=request_id,
        operation_id=operation_id,
    )


@mcp.tool(
    description=(
        "Read a Product System model graph from the active database and report "
        "nodes, edges, broken links, and disconnected nodes. Optional timeout_sec "
        "(300-7200) sets the IPC session budget and the Product System HTTP read."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
@ipc_tool("get_model_graph")
def get_model_graph(
    product_system: str,
    expected_process_ids: list[str] | None = None,
    timeout_sec: int | None = None,
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
        "category names, UUIDs, amounts, units, settings, and resource-release status. "
        "Optional timeout_sec (300-7200) sets the IPC session budget."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
@ipc_tool("calculate_product_system")
def calculate_product_system(
    product_system: str,
    impact_method: str,
    amount: float = 1.0,
    allocation: Literal["physical", "economic", "causal", "none", "default"]
    | None = None,
    regionalized: bool = False,
    costs: bool = False,
    parameters: dict[str, float] | None = None,
    timeout_sec: int | None = None,
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


@mcp.tool(
    description=(
        "Preview or delete ProductSystem, Process, and Flow entities under the "
        "configured project category. Use confirm=false to list scope only; "
        "confirm=true executes deletion. Optional timeout_sec (300-7200) sets the IPC "
        "session budget."
    ),
    annotations=DESTRUCTIVE_ANNOTATIONS,
    structured_output=True,
)
@ipc_tool("cleanup_output")
def cleanup_output(
    target_category: str,
    confirm: bool = False,
    operation_dir: str | None = None,
    timeout_sec: int | None = None,
) -> dict[str, Any]:
    host, port = _endpoint_config()
    category = _target_category(target_category)
    result = run_cleanup_output(host, port, category, confirm=confirm)
    if confirm and result.get("ok") and operation_dir is not None:
        operations.reconcile_cleanup(Path(operation_dir), host, port, category)
    return result


@mcp.tool(
    description=(
        "Search up to 50 keywords in one descriptor scan; serial and paginated per "
        "keyword. Optional timeout_sec (300-7200) sets the IPC session budget."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
@ipc_tool("query_descriptors_batch")
def query_descriptors_batch(
    entity_type: str,
    searches: list[str],
    limit: int = 20,
    offset: int = 0,
    timeout_sec: int | None = None,
) -> dict[str, Any]:
    host, port = _endpoint_config()
    return readonly.query_descriptors_batch(
        host, port, entity_type, searches, limit, offset
    )


@mcp.tool(
    description=(
        "Validate up to 200 exact process_id/flow_id pairs; repeated processes are "
        "read once. Geography is diagnostic. Optional timeout_sec (300-7200) sets "
        "the IPC session budget."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
@ipc_tool("validate_providers_batch")
def validate_providers_batch(
    requirements: list[dict[str, str]],
    timeout_sec: int | None = None,
) -> dict[str, Any]:
    host, port = _endpoint_config()
    return readonly.validate_providers_batch(host, port, requirements)


if __name__ == "__main__":
    mcp.run()
