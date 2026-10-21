from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_rules_layout():
    g = ROOT / "harness/rules/global"
    assert sorted(p.name for p in g.glob("*.yaml")) and not list(g.glob("*.md"))
    for role in ("executor", "reviewer"):
        data = yaml.safe_load((ROOT / "harness/rules/roles" / f"{role}.yaml").read_text(encoding="utf-8"))
        assert data["prompt"].strip() and set(data["access"]) <= {"read", "write"}
        assert data["deliver"]["submit"] in ("artifact", "verdict")


def test_skills_dir_exists():
    assert (ROOT / "harness/tools/skills").is_dir()


def test_category_constant():
    from backend.v5.layout import OPENLCA_PROJECT_CATEGORY

    assert OPENLCA_PROJECT_CATEGORY == "202606-harness-agent-LCA"
