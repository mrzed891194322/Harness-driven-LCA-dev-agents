"""V2 entrypoints used by GUI initialization and cleanup (no evidence wrap)."""

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
        result = run_cleanup_output(
            host, port, category, confirm=confirm, workspace=workspace
        )
        if confirm and result.get("ok"):
            if workspace is None:
                raise ValueError(
                    "workspace is required when confirm=True so cleanup can "
                    "reconcile the import-operations journal"
                )
            root = Path(workspace)
            runs = root / "runs"
            if runs.is_dir():
                for journal_parent in sorted(runs.rglob("import-operations")):
                    if not journal_parent.is_dir():
                        continue
                    if "_run" in journal_parent.parts:
                        continue
                    reconcile_cleanup(journal_parent, host, port, category)
        return result

    perform.__name__ = "cleanup_output_confirm" if confirm else "cleanup_output_preview"
    runner: Callable[..., Any] = serialized_ipc(perform, long_running=True)
    return runner(host, port)
