"""GUI 组件、事件处理器和业务函数共用的全局配置。

GUI 源码位于 ``src/GUI``，运行时 workspace 位于仓库根目录。这里集中声明
界面字体、模板、运行产物和维护脚本的位置，确保从不同工作目录启动 GUI 时，
所有路径仍指向同一套项目资源。
"""

from pathlib import Path


# -----------------------------------------------------------------------------
# 基础目录
# GUI_ROOT 定位 GUI 源码；PROJECT_ROOT 定位仓库并作为其他绝对路径的起点。
# -----------------------------------------------------------------------------
GUI_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = next(
    parent
    for parent in GUI_ROOT.parents
    if (parent / "pyproject.toml").is_file()
)

# -----------------------------------------------------------------------------
# 界面字体
# 两个字体栈由 ui/ui_main.py 注入 CSS：普通字体用于界面与 Markdown，
# 等宽字体用于代码片段和终端；均优先使用本地字体，不依赖在线服务。
# -----------------------------------------------------------------------------
GUI_FONT_FAMILY = (
    '"Libertinus Serif", "Linux Libertine O", "Source Serif 4", '
    '"Noto Serif", Georgia, "Times New Roman", "Noto Serif CJK SC", '
    '"Songti SC", STSong, SimSun, serif'
)
GUI_MONO_FONT_FAMILY = (
    '"JetBrains Mono", "Cascadia Mono", Consolas, Monaco, '
    '"Courier New", monospace'
)

# -----------------------------------------------------------------------------
# workspace 基础目录
# inputs/ 仅保存 plan.md 与 revise.md；memory/ 与 outputs/ 为运行产物。
# -----------------------------------------------------------------------------
WORKSPACE_INPUTS = PROJECT_ROOT / "workspace" / "inputs"
WORKSPACE_MEMORY = PROJECT_ROOT / "workspace" / "memory"
WORKSPACE_OUTPUTS = PROJECT_ROOT / "workspace" / "outputs"
REPORTS_DIR = WORKSPACE_OUTPUTS / "reports"

# -----------------------------------------------------------------------------
# Markdown 文档
# 相对路径用于界面来源/错误提示并构造绝对路径；绝对路径用于实际读取和下载。
# CURRENT_PLAN_PATH 是唯一执行计划；CURRENT_REVISION_PATH 是 revise-lca
# 固定意见输入。两者都只在对应执行按钮被点击后写入。
# -----------------------------------------------------------------------------
PLAN_INPUT_TEMPLATE_RELATIVE_PATH = (
    Path("src") / "GUI" / "ui" / "assets" / "template" / "plan.md"
)
PLAN_INPUT_TEMPLATE_PATH = PROJECT_ROOT / PLAN_INPUT_TEMPLATE_RELATIVE_PATH

REVISE_TEMPLATE_RELATIVE_PATH = (
    Path("src") / "GUI" / "ui" / "assets" / "template" / "revise.md"
)
REVISE_TEMPLATE_PATH = PROJECT_ROOT / REVISE_TEMPLATE_RELATIVE_PATH

CURRENT_PLAN_PATH = WORKSPACE_INPUTS / "plan.md"
CURRENT_REVISION_PATH = WORKSPACE_INPUTS / "revise.md"

LCI_MAPPING_RELATIVE_PATH = (
    Path("workspace") / "outputs" / "LCI" / "human_readable_mapping.md"
)
LCI_MAPPING_FILE_PATH = PROJECT_ROOT / LCI_MAPPING_RELATIVE_PATH

LCA_REPORT_RELATIVE_PATH = (
    Path("workspace") / "outputs" / "reports" / "lca_report.md"
)
LCA_REPORT_PATH = PROJECT_ROOT / LCA_REPORT_RELATIVE_PATH

# -----------------------------------------------------------------------------
# Whole-LCA 结构化运行产物
# 总 manifest 判断运行终态；阶段和审查目录汇总失败原因；报告区文件用于确认
# openLCA 导入、模型图、LCIA 原始结果及计算是否完整。
# -----------------------------------------------------------------------------
WORKFLOW_MANIFEST_PATH = WORKSPACE_MEMORY / "manifest.json"
WORKFLOW_STAGES_DIR = WORKSPACE_MEMORY / "stages"
WORKFLOW_REVIEWS_DIR = WORKSPACE_MEMORY / "reviews"
IMPORT_REPORT_PATH = REPORTS_DIR / "import_report.json"
MODEL_GRAPH_DIR = REPORTS_DIR / "model_graph"
RAW_RESULTS_DIR = REPORTS_DIR / "raw"
CALCULATION_MANIFEST_PATH = REPORTS_DIR / "calculation_manifest.json"

# -----------------------------------------------------------------------------
# 用户上传目录
# GUI 侧栏用户资料在执行前经 file_sync 写入 harness/knowledge/（扁平目录）。
# -----------------------------------------------------------------------------
KNOWLEDGE_DIR = PROJECT_ROOT / "harness" / "knowledge"
USER_UPLOAD_DIR = KNOWLEDGE_DIR
