from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_rules_layout():
    g = ROOT / "harness/rules/global"
    assert sorted(p.name for p in g.glob("*.yaml")) and not list(g.glob("*.md"))
    for role in ("executor", "reviewer"):
        data = yaml.safe_load((ROOT / "harness/workflows/agents" / f"{role}.yaml").read_text(encoding="utf-8"))
        assert data["prompt"].strip() and set(data["access"]) <= {"read", "write"}
        assert data["deliver"]["submit"] in ("artifact", "verdict")


def test_skills_dir_exists():
    assert (ROOT / "harness/tools/skills").is_dir()


def test_category_constant():
    from backend.workflow.layout import OPENLCA_PROJECT_CATEGORY

    assert OPENLCA_PROJECT_CATEGORY == "202606-harness-agent-LCA"


def test_workflows_three_levels():
    """I-50: orchestrations / nodes / agents; no orchestration YAML left at the workflows root."""
    w = ROOT / "harness/workflows"
    assert {"full-lca.yaml", "revise-lca.yaml"} <= {p.name for p in (w / "orchestrations").glob("*.yaml")}
    assert not list(w.glob("*.yaml"))
    assert {"executor.yaml", "reviewer.yaml"} <= {p.name for p in (w / "agents").glob("*.yaml")}
    assert not (ROOT / "harness/rules/roles").exists()


def test_benchmark_harness_holds_eval_workflows():
    product = {p.name for p in (ROOT / "harness/workflows/orchestrations").glob("*.yaml")}
    assert "bom-extract.yaml" not in product
    assert (ROOT / ".benchmark/harness/workflows/orchestrations/bom-extract.yaml").is_file()
    assert (ROOT / ".benchmark/harness/specs/bom-claims.yaml").is_file()

