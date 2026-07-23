from pathlib import Path
from typing import Generator, List, Any, Union
from functions.project_init.private_utils.clean import run_clean_project
from functions.project_init.private_utils.file_handler import copy_uploaded_files
from functions.project_init.private_utils.init_rag import run_initialization
from functions.utils.path_utils import find_project_root

def main(
    ref_materials: Union[List[Any], Any, None],
    ref_data: Union[List[Any], Any, None]
) -> Generator[tuple[str, str], None, None]:
    """
    整合项目初始化的三个步骤：
    1. 调用 clean_dir 清理项目
    2. 将文件交换区上传的文件存放在 harness/knowledge/inputs/user_file 和 harness/knowledge/inputs/user_data 中
    3. 调用 scripts/initialization
    """
    project_root = find_project_root(Path(__file__))
    
    from functions.utils.process_manager import should_stop
 
    accumulated_output = ""
     
    # 步骤 1：清理项目
    yield accumulated_output + "[System] Step 1/3: Cleaning project...\n", "Running"
    for chunk in run_clean_project(project_root):
        if should_stop():
            break
        accumulated_output += chunk
        yield accumulated_output, "Running"
         
    if should_stop():
        if not accumulated_output.endswith("已停止\n") and not accumulated_output.endswith("已停止"):
            accumulated_output += "\n[System] 已停止\n"
        yield accumulated_output, "Stopped"
        return
 
    # 步骤 2：将上传文件移动到 user_file 与 user_data
    accumulated_output += "\n"
    yield accumulated_output + "[System] Step 2/3: Copying uploaded files to target directories...\n", "Running"
    for chunk in copy_uploaded_files(ref_materials, ref_data, project_root):
        if should_stop():
            break
        accumulated_output += chunk
        yield accumulated_output, "Running"
        
    if should_stop():
        if not accumulated_output.endswith("已停止\n") and not accumulated_output.endswith("已停止"):
            accumulated_output += "\n[System] 已停止\n"
        yield accumulated_output, "Stopped"
        return
        
    # 步骤 3：调用项目初始化脚本
    accumulated_output += "\n"
    yield accumulated_output + "[System] Step 3/3: Running initialization script...\n", "Running"
    for chunk in run_initialization(project_root):
        if should_stop():
            break
        accumulated_output += chunk
        yield accumulated_output, "Running"
        
    if should_stop():
        if not accumulated_output.endswith("已停止\n") and not accumulated_output.endswith("已停止"):
            accumulated_output += "\n[System] 已停止\n"
        yield accumulated_output, "Stopped"
    else:
        yield accumulated_output + "\n[System] Project initialization complete.\n", "Finished"
