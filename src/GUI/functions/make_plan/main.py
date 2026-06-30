from pathlib import Path
from typing import Generator
from functions.utils.file_loader.main import main as run_file_loader_action
from functions.utils.path_utils import find_project_root

def main(values: list[str]) -> Generator[tuple[str, str], None, None]:
    """
    1. 将当前渲染 of md 计划内容保存到 src/plan/current_plan.md 中。
    2. 后续功能暂时不做，预留接口。
    """
    import config
    
    template_path = config.PLAN_INPUT_TEMPLATE_PATH
    current_plan_path = config.CURRENT_PLAN_PATH
    
    # 1. 保存当前界面的文本框输入（渲染 of md 计划内容）到 src/plan/current_plan.md
    yield "[System] 正在保存当前渲染的 md 计划内容...\n", "Running"
    
    success = run_file_loader_action(
        "save_values",
        template_path=template_path,
        target_path=current_plan_path,
        values=values
    )
    
    if success:
        saved_msg = f"[System] 成功将当前渲染的 md 计划内容保存到: {current_plan_path}\n"
        yield saved_msg, "Running"
    else:
        yield "[Error] 保存计划内容失败！\n", "Failed"
        return
        
    # 2. 执行 opencode run --command make-plan
    from functions.utils.executor.private_utils.executor_utils import run_opencode_command_console
    
    yield saved_msg + "[System] 正在启动 opencode 执行 make-plan 任务...\n", "Running"
    
    status_val = "Running"
    for log_chunk, status_val in run_opencode_command_console("make-plan"):
        yield saved_msg + log_chunk, status_val
        
    # 3. 后续功能预留接口 (例如在 make-plan 顺利执行完毕后，进一步实现其他后续新功能)
    if status_val == "Finished":
        # TODO: 未来在此处实现更多新功能
        pass
