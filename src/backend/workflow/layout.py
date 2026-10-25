"""Fixed v5 layout constants.

Product harness lives under ``harness/``. Extra trees (same sub-layout) can sit
outside it; loaders resolve short names across these roots. Default extra root:
``.benchmark/harness`` (eval workflows / specs). Agents / rules stay product-side.
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

# Extra harness-shaped trees (repo-relative). Short-name lookup prefers these
# over ``harness/`` so eval variants do not live inside the product tree.
# Future GUI-uploaded overlays can append here without changing call sites.
EXTRA_HARNESS_ROOTS: tuple[Path, ...] = (Path(".benchmark/harness"),)

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


def harness_roots() -> tuple[Path, ...]:
    """Search order for short-name orch / node / spec: extras first, then product."""
    return (*EXTRA_HARNESS_ROOTS, Path("harness"))


def orch_dirs() -> tuple[Path, ...]:
    return tuple(r / "workflows" / "orchestrations" for r in harness_roots())


def node_dirs() -> tuple[Path, ...]:
    return tuple(r / "workflows" / "nodes" for r in harness_roots())


def spec_dirs() -> tuple[Path, ...]:
    return tuple(r / "specs" for r in harness_roots())
