from __future__ import annotations

import functools
import inspect
import os
import sys
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from mcp.server import MCPServer
from mcp_types import ToolAnnotations

CONTROL_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = CONTROL_ROOT.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from harness.tools.control_openlca.utils import operations, readonly
from harness.tools.control_openlca.utils.cleanup import run_cleanup_output
from harness.tools.control_openlca.utils.connection import (
    ipc_budget_scope,
    resolve_ipc_tool_timeout_sec,
)
from harness.tools.control_openlca.utils.guard import serialized_ipc

_LONG_RUNNING_MCP_TOOLS = frozenset(
    {
        "preflight_import_lci",
        "import_lci",
        "get_model_graph",
        "calculate_product_system",
        "cleanup_output",
    }
)
LCA_CONTROL_OPENLCA_MCP = "LCA_CONTROL_OPENLCA_MCP"
from harness.tools.control_openlca.utils.readonly import (
    get_flow_providers as run_get_flow_providers,
)
from harness.tools.control_openlca.utils.readonly import (
    get_process_details as run_get_process_details,
)
from harness.tools.control_openlca.utils.readonly import (
    health_check as run_health_check,
)
from harness.tools.control_openlca.utils.readonly import (
    query_descriptors as run_query_descriptors,
)
from harness.tools.control_openlca.utils.workflow import (
    calculate_product_system as run_calculate_product_system,
)
from harness.tools.control_openlca.utils.workflow import (
    get_model_graph as run_get_model_graph,
)
from harness.tools.lca_artifacts.store import Context, invoke


def _require_mcp_stdio_channel() -> None:
    if os.getenv(LCA_CONTROL_OPENLCA_MCP) != "1":
        raise ValueError(
            "须通过 MCP 调用 control_openlca 工具，禁止 bash 或 Python 直调 "
            "harness.tools.control_openlca.main"
        )


def v2_tool(name):
    def decorate(function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            def execute():
                _require_mcp_stdio_channel()
                context = Context.environment()
                if context.role == "reviewer" and name in {
                    "import_lci",
                    "calculate_product_system",
                    "cleanup_output",
                }:
                    raise ValueError("reviewer may not import, calculate or clean")
                bound = inspect.signature(function).bind_partial(*args, **kwargs)
                bound.apply_defaults()
                params = dict(bound.arguments)
                timeout_raw = params.pop("timeout_sec", None)
                applied_budget = None
                if name in _LONG_RUNNING_MCP_TOOLS:
                    applied_budget = resolve_ipc_tool_timeout_sec(
                        None if timeout_raw is None else int(timeout_raw)
                    )

                def run_call():
                    if name == "get_import_operation":
                        result = function(**params)
                    else:
                        host, port = _endpoint_config()
                        runner = serialized_ipc(
                            lambda host, port: function(**params),
                            long_running=name in _LONG_RUNNING_MCP_TOOLS,
                        )
                        result = runner(host, port)
                    if applied_budget is not None and isinstance(result, dict):
                        result["applied_timeout_sec"] = int(applied_budget)
                    return result

                if applied_budget is not None:
                    with ipc_budget_scope(applied_budget):
                        return run_call()
                return run_call()

            try:
                arguments = dict(
                    inspect.signature(function).bind(*args, **kwargs).arguments
                )
            except TypeError:
                arguments = kwargs
            return invoke(name, execute, arguments=arguments)

        return wrapped

    return decorate


mcp = MCPServer(
    "openLCA-Control",
    instructions=(
        "Query and gated workflow access to the openLCA IPC Server configured "
        "with OPENLCA_IPC_HOST and OPENLCA_IPC_PORT. import_lci and cleanup_output "
        "are destructive; import_lci requires a matching current import scope. "
        "Long-running tools accept optional timeout_sec (300-7200) for IPC session "
        "budget; do not wrap tools in shell timeout."
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


def _workflow_lci_dir(lci_dir: str) -> Path:
    """Limit MCP imports to canonical LCI or a workflow compatibility directory."""
    project_root = PROJECT_ROOT.resolve()
    workspace_root = Path(
        os.getenv("LCA_WORKSPACE", str(project_root / "workspace"))
    ).resolve()
    configured = Path(lci_dir)
    if not configured.is_absolute() and configured.parts[:1] == ("workspace",):
        candidate = workspace_root.joinpath(*configured.parts[1:])
    else:
        candidate = (
            configured if configured.is_absolute() else project_root / configured
        )
    resolved = candidate.resolve()
    canonical = workspace_root / "outputs" / "LCI"
    temporary_root = workspace_root / "tmp"
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
@v2_tool("health_check")
def health_check() -> dict[str, Any]:
    """Check the configured openLCA IPC Server without modifying data."""
    host, port = _endpoint_config()
    return run_health_check(host, port)


@mcp.tool(
    description="Search descriptors in the active openLCA database and return names, UUIDs, categories, and pagination metadata.",
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
@v2_tool("query_descriptors")
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
@v2_tool("get_process_details")
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
@v2_tool("get_flow_providers")
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
        "create/overwrite/delete scope. This tool performs no database writes. "
        "Optional timeout_sec (300-7200) sets the IPC session budget for slow databases."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
@v2_tool("preflight_import_lci")
def preflight_import_lci(
    lci_dir: str = "workspace/outputs/LCI",
    target_category: str = "",
    database_name: str | None = None,
    timeout_sec: int | None = None,
) -> dict[str, Any]:
    """Create a read-only import preflight for the workflow-owned LCI directory."""
    host, port = _endpoint_config()
    context = Context.environment()
    return operations.preflight(
        host=host,
        port=port,
        lci_dir=_workflow_lci_dir(lci_dir),
        target_category=_target_category(target_category),
        database_name=database_name,
        operation_dir=context.safe(context.workspace / "memory" / "import-operations"),
        run_id=context.run_id,
    )


@mcp.tool(
    description=(
        "Destructively import canonical workspace/outputs/LCI or a compatibility LCI "
        "under workspace/tmp after rerunning preflight. Rejects the write when the "
        "database name, target category, or LCI directory does not match the last "
        "successful preflight scope. Optional timeout_sec (300-7200) extends the IPC "
        "session budget; do not wrap this tool in shell timeout."
    ),
    annotations=DESTRUCTIVE_ANNOTATIONS,
    structured_output=True,
)
@v2_tool("import_lci")
def import_lci(
    request_id: str,
    preflight_id: str,
    lci_dir: str = "workspace/outputs/LCI",
    target_category: str = "",
    database_name: str | None = None,
    timeout_sec: int | None = None,
) -> dict[str, Any]:
    """Import LCI under a precise, current preflight scope."""
    host, port = _endpoint_config()
    context = Context.environment()
    from harness.tools.lca_artifacts.checks import (
        require_approved_model,
        require_import_directory,
    )

    require_approved_model(context)
    require_import_directory(context, _workflow_lci_dir(lci_dir))
    return operations.import_request(
        host=host,
        port=port,
        lci_dir=_workflow_lci_dir(lci_dir),
        target_category=_target_category(target_category),
        database_name=database_name,
        operation_dir=context.safe(context.workspace / "memory" / "import-operations"),
        run_id=context.run_id,
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
@v2_tool("get_import_operation")
def get_import_operation(
    request_id: str | None = None, operation_id: str | None = None
) -> dict[str, Any]:
    """Read an import journal without writing to openLCA."""
    context = Context.environment()
    return operations.get_operation(
        context.safe(context.workspace / "memory" / "import-operations"),
        run_id=context.run_id,
        request_id=request_id,
        operation_id=operation_id,
    )


@mcp.tool(
    description=(
        "Read a Product System model graph from the active database and report "
        "nodes, edges, broken links, and disconnected nodes. Optional timeout_sec "
        "(300-7200) sets the IPC session budget."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
@v2_tool("get_model_graph")
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
@v2_tool("calculate_product_system")
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
    from harness.tools.lca_artifacts.checks import (
        require_approved_model,
        require_calculation_plan,
    )

    require_approved_model(Context.environment())
    require_calculation_plan(
        Context.environment(),
        {
            "product_system": product_system,
            "impact_method": impact_method,
            "amount": amount,
            "allocation": allocation,
            "regionalized": regionalized,
            "costs": costs,
            "parameters": parameters,
        },
    )
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
@v2_tool("cleanup_output")
def cleanup_output(
    target_category: str = "",
    include_supporting: bool = False,
    confirm: bool = False,
    timeout_sec: int | None = None,
) -> dict[str, Any]:
    """Clean workflow-imported entities from the active openLCA database."""
    host, port = _endpoint_config()
    result = run_cleanup_output(
        host=host,
        port=port,
        target_category=_target_category(target_category),
        include_supporting=include_supporting,
        confirm=confirm,
    )
    if confirm and result.get("ok"):
        context = Context.environment()
        operations.reconcile_cleanup(
            context.safe(context.workspace / "memory" / "import-operations"),
            host,
            port,
            _target_category(target_category),
        )
    return result


@mcp.tool(
    description="Search up to 50 keywords in one descriptor scan; serial and paginated per keyword.",
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
@v2_tool("query_descriptors_batch")
def query_descriptors_batch(
    entity_type: str, searches: list[str], limit: int = 20, offset: int = 0
) -> dict[str, Any]:
    host, port = _endpoint_config()
    return readonly.query_descriptors_batch(
        host, port, entity_type, searches, limit, offset
    )


@mcp.tool(
    description="Validate up to 200 exact process_id/flow_id pairs; repeated processes are read once. Geography is diagnostic.",
    annotations=READ_ONLY_ANNOTATIONS,
    structured_output=True,
)
@v2_tool("validate_providers_batch")
def validate_providers_batch(requirements: list[dict[str, str]]) -> dict[str, Any]:
    host, port = _endpoint_config()
    return readonly.validate_providers_batch(host, port, requirements)


if __name__ == "__main__":
    os.environ[LCA_CONTROL_OPENLCA_MCP] = "1"
    mcp.run()
