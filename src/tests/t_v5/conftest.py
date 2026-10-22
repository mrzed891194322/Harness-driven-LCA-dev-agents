from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]

def write_yaml(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def make_node(root: Path, node_id: str, *, requires=(), produces=(), flow=None, agents=None) -> None:
    """Node YAML; ``flow`` omitted = config.default_flow (executor -> reviewer, reject max 3)."""
    data = {"id": node_id, "requires": list(requires), "produces": [dict(p) for p in produces],
            "agents": agents or {"executor": "executor", "reviewer": "reviewer"}}
    if flow is not None:
        data["flow"] = flow
    write_yaml(root / "harness/workflows/nodes" / f"{node_id}.yaml", data)


@pytest.fixture
def v5_root(tmp_path: Path) -> Path:
    """A throwaway project root with the real v5 rules and simple specs."""
    root = tmp_path / "proj"
    shutil.copytree(REPO / "harness/rules", root / "harness/rules")
    shutil.copytree(REPO / "harness/workflows/agents", root / "harness/workflows/agents")
    (root / "harness/knowledge").mkdir(parents=True)
    (root / "harness/tools/skills").mkdir(parents=True)
    (root / "harness/specs").mkdir(parents=True)
    for spec in ("paragraph", "summary"):
        write_yaml(root / "harness/specs" / f"{spec}.yaml", {"description": f"写一份 {spec}。\n", "schema": None, "checks": []})
    (root / "workspace").mkdir()
    return root


@pytest.fixture(autouse=True)
def _isolated_env_file(tmp_path, monkeypatch):
    """Template vars / retry schedule come from a temp .env, never the repo's real one (Q4)."""
    from backend.v5 import config

    env = tmp_path / "test.env"
    env.write_text('HARNESS_LANGUAGE="中文"\nOPENLCA_PROJECT_CATEGORY="202606-harness-agent-LCA"\n', encoding="utf-8")
    monkeypatch.setattr(config, "ENV_FILE", env)
    for key in ("HARNESS_LANGUAGE", "OPENLCA_PROJECT_CATEGORY", "PI_MODEL_RETRY_DELAYS_S"):
        monkeypatch.delenv(key, raising=False)
    return env
