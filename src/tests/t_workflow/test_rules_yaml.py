"""Commit A: YAML rules/roles/specs, {{var}} templating, error locations."""
from __future__ import annotations

import pytest
import yaml

from backend.workflow.config import (
    ConfigError,
    load_global_rules,
    load_node,
    load_agent_def,
    load_rule,
    load_spec,
    render,
)
from backend.workflow.inject import Injector
from tests.t_workflow.conftest import REPO, make_node, write_yaml, node_ref, spec_ref


def test_real_harness_rules_roles_specs_load():
    rules = load_global_rules(REPO, "executor")
    assert [r.order for r in rules] == sorted(r.order for r in rules)
    text = "\n".join(r.prompt for r in rules)
    assert "{{" not in text and "中文" in text and "202606-harness-agent-LCA" in text
    for folder in ("lca", "delivery"):
        for p in (REPO / "harness/rules" / folder).glob("*.yaml"):
            load_rule(REPO, str(p.relative_to(REPO / "harness")))
    status = load_rule(REPO, "rules/delivery/status.yaml")
    assert status.applies_to == ["executor"]
    assert load_rule(REPO, "rules/delivery/provenance.yaml").applies_to == ["executor", "reviewer"]
    assert load_agent_def(REPO, "reviewer").deliver.submit == "verdict"
    assert load_agent_def(REPO, "executor").deliver.submit == "artifact"
    for p in (REPO / "harness/specs").glob("*.yaml"):
        assert load_spec(REPO, f"harness/specs/{p.name}").prompt.strip()
    assert load_spec(REPO, spec_ref("lca-bom")).schema_["required"] == ["items"]


def test_undefined_variable_names_file_and_variable(wf_root):
    write_yaml(wf_root / "harness/rules/global/50-x.yaml", {"title": "x", "prompt": "用 {{nope}} 写"})
    with pytest.raises(ConfigError, match=r"50-x\.yaml.*\{\{nope\}\}"):
        load_global_rules(wf_root, "executor")
    assert render("a {{ language }}", "f", {"language": "中文"}) == "a 中文"


def test_yaml_error_reports_file_and_line(wf_root):
    bad = wf_root / "harness/rules/global/60-bad.yaml"
    bad.write_text("title: ok\nprompt: |\n  fine\nbroken: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=r"60-bad\.yaml:\d+:\d+"):
        load_global_rules(wf_root, "executor")


def test_enabled_order_and_applies_to(wf_root):
    g = wf_root / "harness/rules/global"
    write_yaml(g / "70-off.yaml", {"title": "关", "enabled": False, "prompt": "OFF-RULE"})
    write_yaml(g / "71-rev.yaml", {"title": "审", "order": 1, "applies_to": ["reviewer"], "prompt": "REVIEW-ONLY"})
    make_node(wf_root, "a", produces=[{"spec": spec_ref("paragraph"), "path": "a/p.md"}])
    node = load_node(wf_root, node_ref("a"))
    inj = Injector(wf_root)
    ex, rv = inj.system(node, "executor"), inj.system(node, "reviewer")
    assert "OFF-RULE" not in ex and "OFF-RULE" not in rv
    assert "REVIEW-ONLY" in rv and "REVIEW-ONLY" not in ex
    assert rv.index("红线") < rv.index("REVIEW-ONLY") < rv.index("语言")  # order 0 < 1 < 10

def test_produce_spec_defaults_to_role_spec(wf_root):
    role = yaml.safe_load((wf_root / "harness/workflows/agents/executor.yaml").read_text(encoding="utf-8"))
    role["deliver"]["spec"] = "harness/specs/summary.yaml"
    write_yaml(wf_root / "harness/workflows/agents/executor.yaml", role)
    make_node(wf_root, "d", produces=[{"path": "d/s.md"}])
    assert load_node(wf_root, node_ref("d")).produces[0].spec == spec_ref("summary")
    make_node(wf_root, "e", produces=[{"spec": spec_ref("paragraph"), "path": "e/p.md"}])
    assert load_node(wf_root, node_ref("e")).produces[0].spec == spec_ref("paragraph")


def test_produce_without_any_spec_is_error(wf_root):
    make_node(wf_root, "f", produces=[{"path": "f/x.md"}])
    with pytest.raises(ConfigError, match="no spec"):
        load_node(wf_root, node_ref("f"))
