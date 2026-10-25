"""Fixed v5 layout constants.

Product harness lives under ``harness/``. Eval variants live under
``.benchmark/harness/`` (same sub-layout). Orchestration **API ids** are still
file stems discovered by scanning both orch folders; YAML ``nodes:`` /
``produces.spec`` refs are always **repo-root-relative paths** (no short-name
lookup, no extras-first fallback). Agents / rules stay product-side.
"""
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

# Folders scanned for API orch ids (list_workflows / start by stem) and for
# GUI listing / FS read grants. Not used to resolve short node/spec names.
ORCH_SCAN_DIRS: tuple[Path, ...] = (
    Path("harness/workflows/orchestrations"),
    Path(".benchmark/harness/workflows/orchestrations"),
)
NODE_SCAN_DIRS: tuple[Path, ...] = (
    Path("harness/workflows/nodes"),
    Path(".benchmark/harness/workflows/nodes"),
)
SPEC_SCAN_DIRS: tuple[Path, ...] = (
    Path("harness/specs"),
    Path(".benchmark/harness/specs"),
)

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


def orch_dirs() -> tuple[Path, ...]:
    return ORCH_SCAN_DIRS


def node_dirs() -> tuple[Path, ...]:
    return NODE_SCAN_DIRS


def spec_dirs() -> tuple[Path, ...]:
    return SPEC_SCAN_DIRS
