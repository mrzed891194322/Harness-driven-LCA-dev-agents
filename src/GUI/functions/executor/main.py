from typing import Generator
from functions.executor.private_utils.executor_utils import run_opencode_command_console

def run_executor_flow(
    command_name: str,
    user_requirements: str | None = None,
    *,
    requires_input: bool = False,
) -> Generator[tuple[str, str], None, None]:
    """
    运行指定的 OpenCode 命令（Gradio 控制台执行器入口）。
    """
    yield from run_opencode_command_console(
        command_name=command_name,
        user_requirements=user_requirements,
        requires_input=requires_input
    )
