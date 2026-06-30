from pathlib import Path
from typing import Generator
from functions.utils.file_loader.main import main as run_file_loader_action
from functions.utils.path_utils import find_project_root

def main(values: list[str]) -> Generator[tuple[str, str], None, None]:
    """
    1. 将当前界面填写的待完善清单内容保存到 src/plan/todo_list.md 中。
    2. 执行 opencode run --command revise-plan 启动 plan-maker agent 对已生成的计划进行修改。
    """
    import config
    todo_list_path = config.PLAN_MODIFY_FILE_PATH
    
    yield "[System] 正在保存待完善清单修改内容...\n", "Running"
    
    # 动态解析 todo_list.md 以获取实际需要的 textbox 数量，并裁剪 values 列表
    try:
        blocks = run_file_loader_action("parse_template", filepath=todo_list_path)
        expected_tb_count = sum(1 for b in blocks if b["type"] == "textbox")
        values = values[:expected_tb_count]
    except Exception:
        pass
        
    # 保存 values 填入至 todo_list.md 自自身中。
    success = run_file_loader_action(
        "save_values",
        template_path=todo_list_path,
        target_path=todo_list_path,
        values=values
    )
    
    if success:
        saved_msg = f"[System] 成功将修改后的待完善清单保存到: {todo_list_path}\n"
        yield saved_msg, "Running"
    else:
        yield "[Error] 保存待完善清单失败！\n", "Failed"
        return
        
    from functions.utils.executor.private_utils.executor_utils import run_opencode_command_console
    
    yield saved_msg + "[System] 正在启动 opencode 执行 revise-plan 任务...\n", "Running"
    
    status_val = "Running"
    for log_chunk, status_val in run_opencode_command_console("revise-plan"):
        yield saved_msg + log_chunk, status_val
