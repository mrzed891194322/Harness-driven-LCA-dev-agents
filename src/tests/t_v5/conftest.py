from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]

EXEC_REVIEW_FLOW = {
    "start": "executor",
    "max_rounds": 3,
    "edges": [
        {"from": "executor", "on": "submitted", "to": "reviewer"},
        {"from": "executor", "on": "checks_failed", "to": "executor"},
        {"from": "executor", "on": "stop", "to": "failed"},
        {"from": "reviewer", "on": "pass", "to": "done"},
        {"from": "reviewer", "on": "reject", "to": "executor"},
        {"from": "reviewer", "on": "stop", "to": "failed"},
    ],
}


def write_yaml(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def make_node(root: Path, node_id: str, *, requires=(), produces=(), flow=None, agents=None) -> None:
    write_yaml(
        root / "harness/workflows/nodes" / f"{node_id}.yaml",
        {
            "id": node_id,
            "requires": list(requires),
            "produces": [dict(p) for p in produces],
            "agents": agents
            or {"executor": {"role": "executor"}, "reviewer": {"role": "reviewer"}},
            "flow": flow or EXEC_REVIEW_FLOW,
        },
    )


@pytest.fixture
def v5_root(tmp_path: Path) -> Path:
    """A throwaway project root with the real v5 rules and simple specs."""
    root = tmp_path / "proj"
    shutil.copytree(REPO / "harness/rules", root / "harness/rules")
    (root / "harness/knowledge").mkdir(parents=True)
    (root / "harness/tools/skills").mkdir(parents=True)
    (root / "harness/specs").mkdir(parents=True)
    for spec in ("paragraph", "summary"):
        write_yaml(root / "harness/specs" / f"{spec}.yaml", {"description": f"写一份 {spec}。\n", "schema": None, "checks": []})
    (root / "workspace").mkdir()
    return root
