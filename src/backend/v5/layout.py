"""Fixed v5 layout constants."""
from __future__ import annotations

from pathlib import Path

HARNESS_DIRS = ("rules", "specs", "knowledge", "tools", "workflows")
RULES_GLOBAL = Path("harness/rules/global")
SPECS = Path("harness/specs")
KNOWLEDGE = Path("harness/knowledge")
TOOLS_MCP = Path("harness/tools/mcp")
TOOLS_SKILLS = Path("harness/tools/skills")
WORKFLOWS = Path("harness/workflows")
NODES = WORKFLOWS / "nodes"
ORCHESTRATIONS = WORKFLOWS / "orchestrations"
AGENTS = WORKFLOWS / "agents"

WORKSPACE = Path("workspace")
ARTIFACTS = WORKSPACE / "artifacts"
PLAN_DIR = ARTIFACTS / "plan"
RUNS = WORKSPACE / "runs"
RUN_META = RUNS / "_run"

# Host lock 3: openLCA writes only inside this category (single definition).
from harness.tools.shared.control_openlca.category import (  # noqa: E402
    OPENLCA_PROJECT_CATEGORY,  # noqa: E402,F401
)


def node_dir(workspace: Path, node: str) -> Path:
    return workspace / "runs" / node
