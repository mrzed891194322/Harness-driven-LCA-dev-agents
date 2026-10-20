"""Effective read/write scope for one agent: defaults + role access.yaml + node override + host locks.

Host locks (cannot be changed by any configuration):
  1. the plan (workspace/artifacts/plan/**) is always readable and never writable;
  2. writes only to the node's own runs dir and the artifacts subdirs of its ``produces``;
  3. openLCA writes only inside ``OPENLCA_PROJECT_CATEGORY`` (enforced in control_openlca).

The result feeds pi-runtime's PathGuard (tool_call interception) as glob lists; nothing here
goes into the prompt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from backend.v5 import layout
from backend.v5.config import Access, Node

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


def compute_scope(root: Path, node: Node, role: str, role_access: Access) -> Scope:
    ws = root / layout.WORKSPACE
    art = ws / "artifacts"
    agent = node.agents[role]
    toggles = merge_toggles(role_access, agent.access)

    read = {
        str(art / "plan") + "/**",  # lock 1
        str(layout.node_dir(ws, node.id)) + "/**",
        str(root / layout.TOOLS_SKILLS) + "/**",
    }
    for req in node.requires:
        read.add(str(art / req))
        read.add(str(art / req) + "/**")
    for prod in node.produces:
        read.add(str(art / produce_dir(prod.path)) + "/**")
    if toggles["knowledge"]:
        read.add(str(root / layout.KNOWLEDGE) + "/**")
    if toggles["artifacts"]:
        read.add(str(art) + "/**")

    write: set[str] = set()
    if role == "executor":
        write.add(str(layout.node_dir(ws, node.id)) + "/**")
        for prod in node.produces:
            write.add(str(art / produce_dir(prod.path)) + "/**")
    else:
        # reviewer writes only its notes dir inside the node runs dir
        write.add(str(layout.node_dir(ws, node.id) / "reviewer") + "/**")
    denied = [str(art / "plan") + "/**"]  # lock 1 beats everything
    return Scope(sorted(read), sorted(write), denied, toggles)
