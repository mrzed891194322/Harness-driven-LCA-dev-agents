"""Read-only view of the v5 harness YAML for the /harness page (I-21).

Four sections: global rules (plus node-level rule folders), roles, specs, workflows (plus node files).
Each file comes back with its parsed fields, the raw text, and the load error (message + line) if the
real loader rejects it. Nothing is written.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from backend.workflow import config, layout

_LINE = re.compile(r"\.ya?ml:(\d+)(?::\d+)?")

SECTIONS = (
    ("rules", "全局规则"),
    ("agents", "agent"),
    ("specs", "规格"),
    ("workflows", "工作流"),
)


def _entry(root: Path, path: Path, group: str, check: Callable[[], object]) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        fields = yaml.safe_load(raw)
    except yaml.YAMLError:
        fields = None
    error = None
    try:
        check()
    except (config.ConfigError, ValueError, OSError) as exc:
        message = str(exc)
        m = _LINE.search(message)
        error = {"message": message.replace(str(root) + "/", ""), "line": int(m.group(1)) if m else None}
    return {
        "path": path.relative_to(root).as_posix(),
        "name": path.stem,
        "group": group,
        "fields": fields if isinstance(fields, dict) else None,
        "raw": raw,
        "error": error,
    }


def harness_view(root: Path) -> dict[str, Any]:
    harness = root / "harness"
    rules: list[dict[str, Any]] = []
    rules_root = harness / "rules"
    folders = [layout.RULES_GLOBAL.name] + sorted(
        p.name for p in rules_root.iterdir() if p.is_dir() and p.name not in {"global", "roles"}
    ) if rules_root.is_dir() else []
    for folder in folders:
        for path in sorted((rules_root / folder).glob("*.yaml")):
            rel = path.relative_to(harness).as_posix()
            rules.append(_entry(root, path, folder, lambda rel=rel: config.load_rule(root, rel)))
    roles = [
        _entry(root, p, "agents", lambda p=p: config.load_agent_def(root, p.stem))
        for p in sorted((root / layout.AGENTS).glob("*.yaml"))
    ]
    spec_files: list[Path] = []
    seen_specs: set[str] = set()
    for base in layout.spec_dirs():  # product + .benchmark listing; stem de-dupe
        folder = root / base
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("*.yaml")):
            if p.stem in seen_specs:
                continue
            seen_specs.add(p.stem)
            spec_files.append(p)
    specs = [
        _entry(root, p, "specs", lambda p=p: config.load_spec(root, p.relative_to(root).as_posix()))
        for p in spec_files
    ]
    orch_files: list[Path] = []
    seen_orch: set[str] = set()
    for base in layout.orch_dirs():
        folder = root / base
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("*.yaml")):
            if p.stem in seen_orch:
                continue
            seen_orch.add(p.stem)
            orch_files.append(p)
    node_files: list[Path] = []
    seen_nodes: set[str] = set()
    for base in layout.node_dirs():
        folder = root / base
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("*.yaml")):
            if p.stem in seen_nodes:
                continue
            seen_nodes.add(p.stem)
            node_files.append(p)
    workflows = [
        _entry(root, p, "workflows", lambda p=p: config.load_workflow(root, p.stem))
        for p in orch_files
    ] + [
        _entry(root, p, "nodes", lambda p=p: config.load_node(root, p.relative_to(root).as_posix()))
        for p in node_files
    ]
    files = {"rules": rules, "agents": roles, "specs": specs, "workflows": workflows}
    return {
        "sections": [{"id": sid, "title": title, "files": files[sid]} for sid, title in SECTIONS],
        "errors": sum(1 for group in files.values() for f in group if f["error"]),
    }
