"""Fixed v5 layout constants.

Product harness lives under ``harness/``. Eval variants live under
``.benchmark/bom/harness/`` and ``.benchmark/lci/harness/`` (same sub-layout). Orchestration **API ids** are still
file stems discovered by scanning both orch folders; YAML ``nodes:`` /
``produces.spec`` refs are always **repo-root-relative paths** (no short-name
lookup, no extras-first fallback). Rules stay product-side. Agents default to product ``harness/workflows/agents/``; nodes may also path-ref ``.benchmark/.../agents/*.yaml``.
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
    Path(".benchmark/bom/harness/workflows/orchestrations"),
    Path(".benchmark/lci/harness/workflows/orchestrations"),
)
NODE_SCAN_DIRS: tuple[Path, ...] = (
    Path("harness/workflows/nodes"),
    Path(".benchmark/bom/harness/workflows/nodes"),
    Path(".benchmark/lci/harness/workflows/nodes"),
)
SPEC_SCAN_DIRS: tuple[Path, ...] = (
    Path("harness/specs"),
    Path(".benchmark/bom/harness/specs"),
    Path(".benchmark/lci/harness/specs"),
)

WORKSPACE = Path("workspace")
ARTIFACTS = WORKSPACE / "artifacts"
PLAN_DIR = ARTIFACTS / "plan"
RUNS = WORKSPACE / "runs"
RUN_META = RUNS / "_run"
# Per workflow-run deliverables (under workspace root, cleared with runs/_run on prepare_fresh).
RUN_DELIVERABLES_REL = Path("runs") / "_run" / "artifacts"
# Agent-owned intermediates (notes, drafts); cleared with ``runs/_run`` on prepare_fresh.
RUN_NOTES_REL = Path("runs") / "_run" / "notes"

# Injected on bom-extract tiers instead of the LCA ``write_boundary`` bullet in 00-redlines.yaml.
BOM_EXTRACT_WRITE_BOUNDARY_ITEM = (
    "只能写入宿主授予的目录：本节点的 `workspace/runs/_run/notes/<节点>/`（中间笔记与草稿）"
    "和本节点交付物对应的 `workspace/runs/_run/artifacts/<类型>/`。越界读写会被宿主拦截并记录。"
)

# Pi / MCP tool id exposed to the model for harness submit.
SUBMIT_TOOL = "mcp__submit__submit"


def node_uses_run_deliverables(node_or_id) -> bool:
    """bom-extract tiers keep deliverables under ``runs/_run/artifacts/`` (per workflow run)."""
    nid = node_or_id if isinstance(node_or_id, str) else getattr(node_or_id, "id", "")
    return str(nid).startswith("bom-extract-")


def run_deliverables_root(workspace: Path) -> Path:
    return workspace / RUN_DELIVERABLES_REL


def produce_target(workspace: Path, node_or_id, rel: str) -> Path:
    if node_uses_run_deliverables(node_or_id):
        return run_deliverables_root(workspace) / rel
    return workspace / "artifacts" / rel


def produce_write_glob(workspace: Path, node_or_id, rel: str) -> str:
    target = produce_target(workspace, node_or_id, rel)
    base = target.parent if target.suffix else target
    return str(base) + "/**"


def artifacts_root_for_submit(workspace: Path, node_or_id) -> Path:
    if node_uses_run_deliverables(node_or_id):
        return run_deliverables_root(workspace)
    return workspace / "artifacts"


def bom_extract_knowledge_read_paths(root: Path) -> list[str]:
    """Allowlisted knowledge bodies for bom-extract (no README.md index files)."""
    inputs = root / KNOWLEDGE / "inputs"
    if not inputs.is_dir():
        return []
    out: list[str] = []
    for path in sorted(inputs.iterdir()):
        if path.is_file() and path.name.casefold() != "readme.md":
            out.append(str(path))
    return out


# Host lock 3: openLCA writes only inside this category (single definition).
from harness.tools.shared.control_openlca.category import (  # noqa: E402
    OPENLCA_PROJECT_CATEGORY,  # noqa: E402,F401
)


def node_dir(workspace: Path, node: str) -> Path:
    return workspace / "runs" / node


def node_checklist_dir(workspace: Path) -> Path:
    """Per workflow-run checklist store (under ``runs/_run/``; cleared on prepare_fresh)."""
    return workspace / "runs" / "_run" / "checklists"


def node_checklist_path(workspace: Path, node_run_key: str) -> Path:
    return node_checklist_dir(workspace) / f"{node_run_key}.json"


def run_agent_work_dir(workspace: Path, node_run_key: str, agent: str) -> Path:
    """Per-run agent intermediates (notes, drafts); not host status/feedback under ``runs/<node>/``."""
    return workspace / RUN_NOTES_REL / node_run_key / agent


def run_agent_notes_path(workspace: Path, node_run_key: str, agent: str) -> Path:
    return run_agent_work_dir(workspace, node_run_key, agent) / "notes.md"


def agent_intermediate_write_glob(workspace: Path, node, node_run_key: str, agent_key: str) -> str:
    if node_uses_run_deliverables(node):
        return str(run_agent_work_dir(workspace, node_run_key, agent_key)) + "/**"
    return str(node_dir(workspace, node_run_key) / agent_key) + "/**"


def orch_dirs() -> tuple[Path, ...]:
    return ORCH_SCAN_DIRS


def node_dirs() -> tuple[Path, ...]:
    return NODE_SCAN_DIRS


def spec_dirs() -> tuple[Path, ...]:
    return SPEC_SCAN_DIRS
