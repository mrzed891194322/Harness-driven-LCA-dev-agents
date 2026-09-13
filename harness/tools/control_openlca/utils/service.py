"""V2 entrypoints used by GUI initialization and cleanup CLI."""

from harness.tools.lca_artifacts.store import Context, invoke

from .cleanup import run_cleanup_output
from .guard import serialized_ipc
from .operations import reconcile_cleanup
from .readonly import health_check


def health(host, port):
    def execute():
        return serialized_ipc(health_check)(host, port)

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

        return serialized_ipc(perform, long_running=True)(host, port)

    return invoke(
        "cleanup_output",
        execute,
        arguments={"target_category": category, "confirm": confirm},
    )
