from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_rules_layout():
    g = ROOT / "harness/rules/global"
    assert sorted(p.name for p in g.glob("*.md"))
    for role in ("executor", "reviewer"):
        d = ROOT / "harness/rules/roles" / role
        assert (d / "prompt.md").read_text(encoding="utf-8").strip()
        data = yaml.safe_load((d / "access.yaml").read_text(encoding="utf-8"))
        assert set(data) <= {"read", "write"}


def test_skills_dir_exists():
    assert (ROOT / "harness/tools/skills").is_dir()


def test_category_constant():
    from backend.v5.layout import OPENLCA_PROJECT_CATEGORY

    assert OPENLCA_PROJECT_CATEGORY == "202606-harness-agent-LCA"
