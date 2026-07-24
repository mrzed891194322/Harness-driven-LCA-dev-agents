"""Paths shared by the GUI components and event handlers.

The GUI lives below ``src/GUI`` while the runtime contract is rooted at the
repository level.  Keep all paths here so launching the GUI from a different
working directory does not change where it reads or writes data.
"""

from pathlib import Path


GUI_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = next(
    parent
    for parent in GUI_ROOT.parents
    if (parent / "pyproject.toml").is_file()
)

WORKSPACE_INPUTS = PROJECT_ROOT / "workspace" / "inputs"
WORKSPACE_MEMORY = PROJECT_ROOT / "workspace" / "memory"
WORKSPACE_OUTPUTS = PROJECT_ROOT / "workspace" / "outputs"
REFERENCE_INPUTS = WORKSPACE_INPUTS / "references"

# Markdown sources rendered by GUI tabs are configured as project-relative
# paths so repository layout changes only need to be reflected here.
PLAN_INPUT_TEMPLATE_RELATIVE_PATH = (
    Path("src") / "GUI" / "ui" / "assets" / "template" / "plan.md"
)
LCI_MAPPING_RELATIVE_PATH = (
    Path("workspace") / "outputs" / "LCI" / "human_readable_mapping.md"
)
LCA_REPORT_RELATIVE_PATH = (
    Path("workspace") / "outputs" / "reports" / "lca_report.md"
)

# The plan tab has one default source.  It never reads CURRENT_PLAN_PATH when
# the panel opens; that path is written only after the execute action succeeds.
PLAN_INPUT_TEMPLATE_PATH = PROJECT_ROOT / PLAN_INPUT_TEMPLATE_RELATIVE_PATH
CURRENT_PLAN_PATH = WORKSPACE_INPUTS / "plan.md"
PLAN_OUTPUT_FILE_PATH = WORKSPACE_INPUTS / "plan.md"
PLAN_OUTPUT_TEMPLATE_KIND = "lca_plan_input"
PLAN_MODIFY_FILE_PATH = WORKSPACE_INPUTS / "plan.md"
PLAN_MODIFY_TEMPLATE_KIND = "lca_todo_list"

# The LCI mapping is a fixed workflow output location.
LCI_MAPPING_FILE_PATH = PROJECT_ROOT / LCI_MAPPING_RELATIVE_PATH

WORKFLOW_MANIFEST_PATH = WORKSPACE_MEMORY / "manifest.json"
WORKFLOW_STAGES_DIR = WORKSPACE_MEMORY / "stages"
WORKFLOW_REVIEWS_DIR = WORKSPACE_MEMORY / "reviews"
REPORTS_DIR = WORKSPACE_OUTPUTS / "reports"
IMPORT_REPORT_PATH = REPORTS_DIR / "import_report.json"
MODEL_GRAPH_DIR = REPORTS_DIR / "model_graph"
RAW_RESULTS_DIR = REPORTS_DIR / "raw"
CALCULATION_MANIFEST_PATH = REPORTS_DIR / "calculation_manifest.json"
LCA_REPORT_PATH = PROJECT_ROOT / LCA_REPORT_RELATIVE_PATH

# Uploaded files are staged in workspace inputs.  The initialization flow
# synchronizes them to harness/knowledge/inputs/user_ref before RAG builds.
USER_FILE_DIR = REFERENCE_INPUTS / "file"
USER_DATA_DIR = REFERENCE_INPUTS / "data"

# Project maintenance scripts all live below src/scripts.
CLEAN_SCRIPT_PATH = PROJECT_ROOT / "src" / "scripts" / "clean_dir" / "main.py"
FILE_SYNC_SCRIPT_PATH = PROJECT_ROOT / "src" / "scripts" / "file_sync" / "main.py"
INIT_RAG_SCRIPT_PATH = PROJECT_ROOT / "src" / "scripts" / "initialization" / "main.py"
OPENLCA_CHECK_DIR = (
    PROJECT_ROOT / "src" / "scripts" / "initialization" / "openlca_check"
)
