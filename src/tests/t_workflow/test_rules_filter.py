"""Node/agent rules_skip and rules_trim filters (01 PCFBench fidelity)."""
from __future__ import annotations

import yaml

from backend.workflow.config import load_node, load_spec, load_workflow
from backend.workflow.inject import Injector
from tests.t_workflow.conftest import REPO, make_node, node_ref, spec_ref, write_yaml


def test_rules_skip_whole_global_rule(wf_root):
    make_node(wf_root, "skip-lang", produces=[{"spec": spec_ref("paragraph"), "path": "a/p.md"}])
    node_path = wf_root / node_ref("skip-lang")
    data = yaml.safe_load(node_path.read_text(encoding="utf-8"))
    data["rules_skip"] = ["rules/global/10-language.yaml"]
    write_yaml(node_path, data)
    node = load_node(wf_root, node_ref("skip-lang"))
    sys = Injector(wf_root).system(node, "executor")
    assert "# 语言" not in sys and "一律使用" not in sys
    assert "# 红线" in sys


def test_rules_trim_items(wf_root):
    make_node(wf_root, "trim-red", produces=[{"spec": spec_ref("paragraph"), "path": "a/p.md"}])
    node_path = wf_root / node_ref("trim-red")
    data = yaml.safe_load(node_path.read_text(encoding="utf-8"))
    data["rules_trim"] = {"rules/global/00-redlines.yaml": ["openlca_scope", "network_sources"]}
    write_yaml(node_path, data)
    node = load_node(wf_root, node_ref("trim-red"))
    sys = Injector(wf_root).system(node, "executor")
    assert "openLCA" not in sys
    assert "只按 `<plan>`" in sys


def test_bom_01_inject_skips_language_and_uses_plan_not_embedded_doc():
    _, nodes = load_workflow(REPO, "bom-extract-01")
    node = nodes[0]
    specs = {p.spec: load_spec(REPO, p.spec) for p in node.produces}
    inj = Injector(REPO)
    plan_body = (
        "kind: lca_execution_plan\nversion: 2\ntemplate_id: bom-only\nitems:\n"
        "- title: Material/energy extraction\n  content: |\n    What is the mass loss rate?\n"
    )
    inj.plan_override = {"plan.yaml": plan_body}
    sys = inj.system(node, "executor")
    assert "# 语言" not in sys
    assert "openLCA" not in sys
    assert "PCFBench extraction (official)" in sys
    assert "You are an LCA expert extracting" in sys
    assert "plan text in ``<plan>``" in sys
    user = inj(node, "executor", 1, None, specs)
    assert user.startswith("<plan>")
    assert plan_body.strip() in user
    assert "Query:" not in user and "Document text:" not in user
    assert "<inputs>" not in user and "<redo_policy>" not in user
    assert "<deliverable_bom-claims-01>" in user
