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
REFERENCE_INPUTS = WORKSPACE_INPUTS / "references"

# Retained for the disabled legacy plan widgets.  The active workflow uses
# workspace/inputs/plan.md as its sole plan input.
PLAN_INPUT_TEMPLATE_PATH = GUI_ROOT / "ui" / "assets" / "template" / "plan.md"
CURRENT_PLAN_PATH = WORKSPACE_INPUTS / "plan.md"
PLAN_OUTPUT_FILE_PATH = WORKSPACE_INPUTS / "plan.md"
PLAN_OUTPUT_TEMPLATE_KIND = "lca_execution_plan"
PLAN_MODIFY_FILE_PATH = WORKSPACE_INPUTS / "plan.md"
PLAN_MODIFY_TEMPLATE_KIND = "lca_todo_list"

# The LCI mapping is a fixed workflow output location.
LCI_MAPPING_FILE_PATH = (
    PROJECT_ROOT / "workspace" / "outputs" / "LCI" / "human_readable_mapping.md"
)
LCI_MAPPING_TEMPLATE_KIND = "lci_human_readable_mapping"

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
