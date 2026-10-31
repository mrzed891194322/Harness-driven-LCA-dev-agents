"""Effective read/write scope for one agent: defaults + agent template access + node override + host locks.

Host locks (cannot be changed by any configuration):
  1. the plan (workspace/artifacts/plan/**) is always readable and never writable;
  2. writes only to the node's own runs dir and the artifacts subdirs of its ``produces``
     (revise-lca: existing originals / other revs there are write-denied, I-45);
  3. openLCA writes only inside ``OPENLCA_PROJECT_CATEGORY`` (enforced in control_openlca).

The result feeds pi-runtime's PathGuard (tool_call interception) as glob lists; nothing here
goes into the prompt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from backend.workflow import layout
from backend.workflow.config import Access, Node

# toggleable read areas (default on); locked areas are not listed here
READ_TOGGLES = ("knowledge", "artifacts")
LOCKED = ("plan_readable", "write_only_produces", "openlca_project_category")


@dataclass(frozen=True)
class Scope:
    read_globs: list[str]
    write_globs: list[str]
    denied_write_globs: list[str]
    toggles: dict[str, bool] = field(default_factory=dict)
    locked: tuple[str, ...] = LOCKED


def produce_dir(path: str) -> str:
    """Artifacts subdir that a produce entry grants (``bom/bom.json`` -> ``bom``)."""
    first = Path(path).parts[0] if Path(path).parts else ""
    if not first or first in ("..", ".") or first == "plan":
        raise ValueError(f"invalid produces path {path!r}")
    return first


def merge_toggles(*layers: Access) -> dict[str, bool]:
    toggles = {name: True for name in READ_TOGGLES}
    for layer in layers:
        for key, value in layer.read.items():
            if key in toggles:
                toggles[key] = bool(value)
    return toggles


def compute_scope(root: Path, node: Node, agent_key: str, agent_access: Access, workspace: Path | None = None) -> Scope:
    ws = workspace or (root / layout.WORKSPACE)
    art = ws / "artifacts"
    agent = node.agents[agent_key]
    toggles = merge_toggles(agent_access, agent.access)

    read = {
        str(art / "plan") + "/**",  # lock 1
        str(layout.node_dir(ws, node.run_key)) + "/**",
        str(root / layout.TOOLS_SKILLS) + "/**",
    }
    # Path-style tools.skills (repo-root-relative): grant the skill file/dir itself.
    for skill in agent.tools.skills:
        raw = (skill or "").strip()
        if not raw or ("/" not in raw and not raw.startswith(".")):
            continue
        rel = Path(raw)
        if rel.name == "SKILL.md":
            read.add(str(root / rel))
            read.add(str(root / rel.parent) + "/**")
        else:
            read.add(str(root / rel) + "/**")
    for base in layout.spec_dirs():  # product + .benchmark specs (read grant, not name lookup)
        read.add(str(root / base) + "/**")
    for req in node.requires:
        read.add(str(art / req))
        read.add(str(art / req) + "/**")
    for prod in node.produces:
        read.add(str(art / produce_dir(prod.path)) + "/**")
    if toggles["knowledge"]:
        read.add(str(root / layout.KNOWLEDGE) + "/**")
    if toggles["artifacts"]:
        read.add(str(art) + "/**")
    # Specs / skills may cite JSON Schema files and rules outside the produce dirs.
    read.add(str(root / ".benchmark/schemas") + "/**")
    read.add(str(root / "harness/rules") + "/**")

    write: set[str] = set()
    # Writers: Node.is_writer (orthogonal to primary/submit). Non-writers: notes dir only.
    if node.is_writer(agent_key):
        write.add(str(layout.node_dir(ws, node.run_key)) + "/**")
        for prod in node.produces:
            write.add(str(art / produce_dir(prod.path)) + "/**")
    else:
        # reviewer / primary orch / other non-writers: notes dir only
        write.add(str(layout.node_dir(ws, node.run_key) / agent_key) + "/**")
    denied = [str(art / "plan") + "/**"]  # lock 1 beats everything
    if node.rev:
        # rev k: originals and other revs in the produce dirs are write-denied; only rev k is writable
        from backend.workflow.revisions import split

        for d in sorted({produce_dir(p.path) for p in node.produces}):
            parent = art / d
            for item in sorted(parent.iterdir()) if parent.is_dir() else []:
                if split(item.name)[1] != node.rev:
                    denied.append(str(item) + ("/**" if item.is_dir() else ""))
    return Scope(sorted(read), sorted(write), denied, toggles)
