from typing import Generator
from functions.utils.executor.private_utils.executor_utils import (
    run_opencode_command_console,
    run_workflow_command_console,
)

def main(
    command_name: str,
    user_requirements: str | None = None,
    *,
    requires_input: bool = False,
) -> Generator[tuple[str, str], None, None]:
    """
    运行 GUI 工作流或其它 OpenCode 命令（Gradio 控制台执行器入口）。
    """
    if command_name in {"whole-lca", "revise-lca"}:
        yield from run_workflow_command_console(command_name)
        return
    yield from run_opencode_command_console(
        command_name=command_name,
        user_requirements=user_requirements,
        requires_input=requires_input
    )
