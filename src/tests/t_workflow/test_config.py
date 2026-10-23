import pytest

from backend.workflow.config import ConfigError, load_node, load_workflow
from backend.workflow.config import default_flow
from tests.t_workflow.conftest import make_node, write_yaml

EXEC_REVIEW_FLOW = default_flow({"reviewer": 1})


def test_workflow_and_nodes_load(wf_root):
    make_node(wf_root, "a", produces=[{"spec": "paragraph", "path": "text"}])
    make_node(wf_root, "b", requires=["text"], produces=[{"spec": "summary", "path": "summary"}])
    write_yaml(wf_root / "harness/workflows/orchestrations/demo.yaml", {"nodes": ["a", "b"]})
    wf, nodes = load_workflow(wf_root, "demo")
    assert [n.id for n in nodes] == ["a", "b"]
    reject = next(e for e in nodes[0].flow.edges if e.when == "reject")
    assert reject.to == "executor" and reject.max == 3


def test_unknown_node(wf_root):
    write_yaml(wf_root / "harness/workflows/orchestrations/demo.yaml", {"nodes": ["nope"]})
    with pytest.raises(ConfigError, match=r"demo\.yaml:\d+: unknown node 'nope'"):
        load_workflow(wf_root, "demo")


def test_flow_must_reach_done(wf_root):
    flow = {"edges": [{"from": "executor", "when": "done", "to": "failed"}]}
    make_node(wf_root, "a", flow=flow)
    with pytest.raises(ConfigError, match=r"a\.yaml:\d+: flow cannot reach done"):
        load_node(wf_root, "a")


def test_duplicate_edge(wf_root):
    flow = dict(EXEC_REVIEW_FLOW, edges=EXEC_REVIEW_FLOW["edges"] + [EXEC_REVIEW_FLOW["edges"][0]])
    make_node(wf_root, "a", flow=flow)
    with pytest.raises(ConfigError, match=r"a\.yaml:\d+: duplicate"):
        load_node(wf_root, "a")


def test_unknown_when_value(wf_root):
    flow = {"edges": [{"from": "executor", "when": "submitted", "to": "done"}]}
    make_node(wf_root, "a", flow=flow, agents={"executor": "executor"})
    with pytest.raises(ConfigError, match=r"a\.yaml:\d+: when 'submitted' is not a artifact submit value"):
        load_node(wf_root, "a")


def test_back_edge_needs_max(wf_root):
    edges = [dict(e) for e in EXEC_REVIEW_FLOW["edges"]]
    for e in edges:
        e.pop("max", None)
    make_node(wf_root, "a", flow={"edges": edges})
    with pytest.raises(ConfigError, match=r"a\.yaml:\d+: back edge reviewer -> executor needs `max"):
        load_node(wf_root, "a")


def test_mixed_unconditional_and_when(wf_root):
    flow = {"edges": [{"from": "executor", "to": "done"}, {"from": "executor", "when": "blocked", "to": "blocked"}]}
    make_node(wf_root, "a", flow=flow, agents={"executor": "executor"})
    with pytest.raises(ConfigError, match=r"a\.yaml:\d+: 'executor' mixes"):
        load_node(wf_root, "a")


def test_executor_cannot_approve_its_own_redo(wf_root):
    flow = {"edges": [{"from": "executor", "when": "done", "to": "done"},
                      {"from": "executor", "when": "redo_upstream", "to": "redo_upstream"}]}
    make_node(wf_root, "a", flow=flow, agents={"executor": "executor"})
    with pytest.raises(ConfigError, match="redo_needs_reviewer"):
        load_node(wf_root, "a")


def test_free_agent_keys_and_inline_checker(wf_root):
    checker = {"prompt": "只核对单位换算。", "deliver": {"submit": "verdict"}}
    flow = {"start": "writer", "edges": [
        {"from": "writer", "when": "done", "to": "checker"},
        {"from": "checker", "when": "approve", "to": "done"},
        {"from": "checker", "when": "reject", "to": "writer", "max": 2}]}
    make_node(wf_root, "a", produces=[{"spec": "paragraph", "path": "t/t.md"}], flow=flow,
              agents={"writer": "executor", "checker": checker})
    node = load_node(wf_root, "a")
    assert node.role("writer") == "executor" and node.role("checker") == "reviewer"


def test_start_must_be_artifact_agent(wf_root):
    make_node(wf_root, "a", flow={"start": "reviewer", "edges": [{"from": "reviewer", "when": "approve", "to": "done"}]})
    with pytest.raises(ConfigError, match=r"a\.yaml:\d+: flow.start 'reviewer' must be an artifact agent"):
        load_node(wf_root, "a")


def test_rev_is_host_set(wf_root):
    make_node(wf_root, "a")
    p = wf_root / "harness/workflows/nodes/a.yaml"
    p.write_text(p.read_text(encoding="utf-8") + "rev: 1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=r"a\.yaml:\d+: rev is host-set"):
        load_node(wf_root, "a")


def test_unknown_spec(wf_root):
    make_node(wf_root, "a", produces=[{"spec": "missing", "path": "x"}])
    write_yaml(wf_root / "harness/workflows/orchestrations/demo.yaml", {"nodes": ["a"]})
    with pytest.raises(ConfigError, match="spec"):
        load_workflow(wf_root, "demo")


def test_duplicate_node_in_workflow(wf_root):
    make_node(wf_root, "a")
    write_yaml(wf_root / "harness/workflows/orchestrations/demo.yaml", {"nodes": ["a", "a"]})
    with pytest.raises(ConfigError, match="duplicate"):
        load_workflow(wf_root, "demo")


def test_short_name_agents_resolve(wf_root):
    """I-50: `executor: executor` loads harness/workflows/agents/executor.yaml."""
    make_node(wf_root, "a", agents={"executor": "executor", "reviewer": {"agent": "reviewer", "max_turns": 5}})
    node = load_node(wf_root, "a")
    assert node.agents["executor"].definition.deliver.submit == "artifact"
    assert node.agents["reviewer"].definition.deliver.submit == "verdict" and node.agents["reviewer"].max_turns == 5


def test_unknown_agent_name_has_file_and_line(wf_root):
    make_node(wf_root, "a", agents={"executor": "nobody", "reviewer": "reviewer"})
    with pytest.raises(ConfigError, match=r"nodes/a\.yaml:\d+: unknown agent 'nobody'.*known: executor, reviewer"):
        load_node(wf_root, "a")


INLINE_EXEC = {"prompt": "按 <plan> 写段落。", "access": {"read": {"knowledge": False}},
               "deliver": {"submit": "artifact", "spec": "paragraph", "max_turns": 7}}


def test_inline_agent_in_node(wf_root):
    """I-50: an agent object with prompt/deliver is an inline agent; other keys are node overrides."""
    make_node(wf_root, "a", produces=[{"path": "text"}],
              agents={"executor": {**INLINE_EXEC, "tools": {"mcp": ["control_openlca"]}}, "reviewer": "reviewer"})
    node = load_node(wf_root, "a")
    ex = node.agents["executor"]
    assert ex.agent == "" and ex.definition.prompt.startswith("按") and ex.definition.deliver.max_turns == 7
    assert ex.definition.access.read == {"knowledge": False} and ex.tools.mcp == ["control_openlca"]
    assert node.produces[0].spec == "paragraph"  # default spec from the inline deliver


def test_bad_inline_agent_names_file_and_line(wf_root):
    make_node(wf_root, "a", agents={"executor": {"prompt": "x"}, "reviewer": "reviewer"})
    with pytest.raises(ConfigError, match=r"nodes/a\.yaml:\d+: inline agent 'executor' needs 'prompt' and 'deliver'"):
        load_node(wf_root, "a")


def test_orchestration_mixes_names_and_inline_nodes(wf_root):
    make_node(wf_root, "a", produces=[{"spec": "paragraph", "path": "text"}])
    inline = {"id": "b", "requires": ["text"], "produces": [{"spec": "summary", "path": "sum"}],
              "agents": {"executor": "executor", "reviewer": {**INLINE_EXEC, "deliver": {"submit": "verdict"}}},
              "flow": EXEC_REVIEW_FLOW}
    write_yaml(wf_root / "harness/workflows/orchestrations/mix.yaml", {"nodes": ["a", inline]})
    wf, nodes = load_workflow(wf_root, "mix")
    assert wf.nodes == ["a", "b"] and [n.id for n in nodes] == ["a", "b"]
    assert nodes[1].agents["reviewer"].definition.deliver.submit == "verdict"


def test_inline_node_errors(wf_root):
    write_yaml(wf_root / "harness/workflows/orchestrations/bad.yaml", {"nodes": [{"title": "no id"}]})
    with pytest.raises(ConfigError, match=r"orchestrations/bad\.yaml:\d+: inline node #1 needs an 'id'"):
        load_workflow(wf_root, "bad")
    write_yaml(wf_root / "harness/workflows/orchestrations/bad2.yaml", {"nodes": ["ghost"]})
    with pytest.raises(ConfigError, match=r"orchestrations/bad2\.yaml:\d+: unknown node 'ghost'"):
        load_workflow(wf_root, "bad2")


def test_node_override_does_not_touch_template(wf_root):
    """DESIGN §九: {agent: executor, max_turns, tools} applies to that node only."""
    from backend.workflow.config import load_agent_def

    before = load_agent_def(wf_root, "executor").model_dump()
    tpl_text = (wf_root / "harness/workflows/agents/executor.yaml").read_text(encoding="utf-8")
    make_node(wf_root, "a", agents={"executor": {"agent": "executor", "max_turns": 3, "tools": {"mcp": ["control_openlca"]},
                                                 "access": {"read": {"knowledge": False}}}, "reviewer": "reviewer"})
    make_node(wf_root, "b", agents={"executor": "executor", "reviewer": "reviewer"})
    a, b = load_node(wf_root, "a"), load_node(wf_root, "b")
    assert a.agents["executor"].max_turns == 3 and b.agents["executor"].max_turns is None
    assert b.agents["executor"].tools.mcp == [] and b.agents["executor"].access.read == {}
    assert a.agents["executor"].definition.model_dump() == before == b.agents["executor"].definition.model_dump()
    assert a.agents["executor"].definition is not b.agents["executor"].definition
    assert (wf_root / "harness/workflows/agents/executor.yaml").read_text(encoding="utf-8") == tpl_text
