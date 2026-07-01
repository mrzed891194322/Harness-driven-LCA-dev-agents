from pathlib import Path

# 1. 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 2. 计划输入 Tab (Plan Input) 相关文件路径
PLAN_INPUT_TEMPLATE_PATH = PROJECT_ROOT / "src" / "GUI" / "ui" / "assets" / "template" / "plan.md"
CURRENT_PLAN_PATH = PROJECT_ROOT / "src" / "plan" / "current_plan.md"

# 3. 计划输出 Tab (Plan Output) 相关文件路径与模板标识
PLAN_OUTPUT_FILE_PATH = PROJECT_ROOT / "src" / "plan" / "execution_plan.md"
PLAN_OUTPUT_TEMPLATE_KIND = "lca_execution_plan"

# 4. 计划修改 Tab (Plan Modification) 相关文件路径与模板标识
PLAN_MODIFY_FILE_PATH = PROJECT_ROOT / "src" / "plan" / "todo_list.md"
PLAN_MODIFY_TEMPLATE_KIND = "lca_todo_list"

# 5. 材料与数据文件上传的目标保存目录
USER_FILE_DIR = PROJECT_ROOT / "src" / "input" / "user_file"
USER_DATA_DIR = PROJECT_ROOT / "src" / "input" / "user_data"

# 6. 项目初始化与清理相关的外部脚本路径
CLEAN_SCRIPT_PATH = PROJECT_ROOT / "src" / "scripts" / "clean_dir" / "clean_dir.py"
INIT_RAG_SCRIPT_PATH = PROJECT_ROOT / "src" / "scripts" / "initialization" / "main.py"
OPENLCA_CHECK_DIR = PROJECT_ROOT / "src" / "scripts" / "initialization" / "openlca_check"

