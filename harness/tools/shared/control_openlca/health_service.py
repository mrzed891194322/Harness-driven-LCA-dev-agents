"""V2 entrypoints used by GUI initialization and cleanup CLI (no evidence wrap)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from harness.tools.shared.control_openlca.cleanup import run_cleanup_output
from harness.tools.shared.control_openlca.guard import serialized_ipc
from harness.tools.shared.control_openlca.operations import reconcile_cleanup
from harness.tools.shared.control_openlca.readonly import health_check


def health(host: str, port: int) -> dict[str, Any]:
    """Return the raw domain health probe result (ok / attempt_count / …)."""
    runner: Callable[..., Any] = serialized_ipc(health_check)
    return runner(host, port)


def cleanup(
    host: str,
    port: int,
    category: str,
    confirm: bool = False,
    *,
    workspace: Path | str | None = None,
) -> dict[str, Any]:
    """Preview or delete foreground entities; return the raw domain result."""

    def perform(host: str, port: int) -> dict[str, Any]:
        result = run_cleanup_output(host, port, category, confirm=confirm)
        if confirm and result.get("ok"):
            if workspace is None:
                raise ValueError(
                    "workspace is required when confirm=True so cleanup can "
                    "reconcile the import-operations journal"
                )
            root = Path(workspace)
            reconcile_cleanup(
                root / "records" / "import-operations",
                host,
                port,
                category,
            )
        return result

    runner: Callable[..., Any] = serialized_ipc(perform, long_running=True)
    return runner(host, port)
