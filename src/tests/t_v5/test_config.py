import pytest

from backend.v5.config import ConfigError, load_node, load_workflow
from tests.t_v5.conftest import EXEC_REVIEW_FLOW, make_node, write_yaml


def test_workflow_and_nodes_load(v5_root):
    make_node(v5_root, "a", produces=[{"spec": "paragraph", "path": "text"}])
    make_node(v5_root, "b", requires=["text"], produces=[{"spec": "summary", "path": "summary"}])
    write_yaml(v5_root / "harness/workflows/demo.yaml", {"nodes": ["a", "b"]})
    wf, nodes = load_workflow(v5_root, "demo")
    assert [n.id for n in nodes] == ["a", "b"]
    assert nodes[0].transition("reviewer", "reject") == "executor"


def test_unknown_node(v5_root):
    write_yaml(v5_root / "harness/workflows/demo.yaml", {"nodes": ["nope"]})
    with pytest.raises(ConfigError, match="missing file"):
        load_workflow(v5_root, "demo")


def test_flow_must_reach_terminal(v5_root):
    flow = {"edges": [{"from": "executor", "on": "submitted", "to": "executor"}]}
    make_node(v5_root, "a", flow=flow)
    with pytest.raises(ConfigError, match="cannot reach"):
        load_node(v5_root, "a")


def test_duplicate_edge(v5_root):
    flow = dict(EXEC_REVIEW_FLOW, edges=EXEC_REVIEW_FLOW["edges"] + [EXEC_REVIEW_FLOW["edges"][0]])
    make_node(v5_root, "a", flow=flow)
    with pytest.raises(ConfigError, match="duplicate"):
        load_node(v5_root, "a")


def test_unknown_role(v5_root):
    make_node(v5_root, "a", agents={"executor": {"role": "executor"}, "boss": {"role": "executor"}})
    with pytest.raises(ConfigError):
        load_node(v5_root, "a")


def test_unknown_spec(v5_root):
    make_node(v5_root, "a", produces=[{"spec": "missing", "path": "x"}])
    write_yaml(v5_root / "harness/workflows/demo.yaml", {"nodes": ["a"]})
    with pytest.raises(ConfigError, match="spec"):
        load_workflow(v5_root, "demo")


def test_duplicate_node_in_workflow(v5_root):
    make_node(v5_root, "a")
    write_yaml(v5_root / "harness/workflows/demo.yaml", {"nodes": ["a", "a"]})
    with pytest.raises(ConfigError, match="duplicate"):
        load_workflow(v5_root, "demo")
