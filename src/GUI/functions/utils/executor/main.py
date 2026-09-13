from collections.abc import Generator

from functions.utils.executor.private_utils.executor_utils import (
    run_workflow_command_console,
)


def main(
    command_name: str,
    user_requirements: str | None = None,
    *,
    requires_input: bool = False,
) -> Generator[tuple[str, str], None, None]:
    """GUI console executor for whole-lca / revise-lca."""
    del user_requirements, requires_input
    if command_name in {"whole-lca", "revise-lca"}:
        yield from run_workflow_command_console(command_name)
        return
    yield (
        f"[System] Unsupported workflow command: {command_name}\n",
        "Failed",
    )
