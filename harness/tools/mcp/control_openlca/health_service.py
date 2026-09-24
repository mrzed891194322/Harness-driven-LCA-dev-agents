"""V2 entrypoints used by GUI initialization and cleanup CLI."""

from collections.abc import Callable
from typing import Any

from harness.tools.mcp.control_openlca.utils.cleanup import run_cleanup_output
from harness.tools.mcp.control_openlca.utils.guard import serialized_ipc
from harness.tools.mcp.control_openlca.utils.operations import reconcile_cleanup
from harness.tools.mcp.control_openlca.utils.readonly import health_check
from harness.tools.shared.lca_artifacts.store import Context, invoke


def health(host, port):
    def execute():
        runner: Callable[..., Any] = serialized_ipc(health_check)
        return runner(host, port)

    return invoke("health_check", execute)


def cleanup(host, port, category, confirm=False):
    def execute():
        def perform(host, port):
            result = run_cleanup_output(host, port, category, confirm=confirm)
            if confirm and result.get("ok"):
                ctx = Context.environment()
                reconcile_cleanup(
                    ctx.safe(ctx.workspace / "memory" / "import-operations"),
                    host,
                    port,
                    category,
                )
            return result

        runner: Callable[..., Any] = serialized_ipc(perform, long_running=True)
        return runner(host, port)

    return invoke(
        "cleanup_output",
        execute,
        arguments={"target_category": category, "confirm": confirm},
    )
