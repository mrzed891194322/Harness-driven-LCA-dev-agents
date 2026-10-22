import pytest

from backend.v5.config import ConfigError, load_node, load_workflow
from tests.t_v5.conftest import EXEC_REVIEW_FLOW, make_node, write_yaml


def test_workflow_and_nodes_load(v5_root):
    make_node(v5_root, "a", produces=[{"spec": "paragraph", "path": "text"}])
    make_node(v5_root, "b", requires=["text"], produces=[{"spec": "summary", "path": "summary"}])
    write_yaml(v5_root / "harness/workflows/orchestrations/demo.yaml", {"nodes": ["a", "b"]})
    wf, nodes = load_workflow(v5_root, "demo")
    assert [n.id for n in nodes] == ["a", "b"]
    assert nodes[0].transition("reviewer", "reject") == "executor"


def test_unknown_node(v5_root):
    write_yaml(v5_root / "harness/workflows/orchestrations/demo.yaml", {"nodes": ["nope"]})
    with pytest.raises(ConfigError, match=r"demo\.yaml:\d+: unknown node 'nope'"):
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
    make_node(v5_root, "a", agents={"executor": "executor", "boss": "executor"})
    with pytest.raises(ConfigError):
        load_node(v5_root, "a")


def test_unknown_spec(v5_root):
    make_node(v5_root, "a", produces=[{"spec": "missing", "path": "x"}])
    write_yaml(v5_root / "harness/workflows/orchestrations/demo.yaml", {"nodes": ["a"]})
    with pytest.raises(ConfigError, match="spec"):
        load_workflow(v5_root, "demo")


def test_duplicate_node_in_workflow(v5_root):
    make_node(v5_root, "a")
    write_yaml(v5_root / "harness/workflows/orchestrations/demo.yaml", {"nodes": ["a", "a"]})
    with pytest.raises(ConfigError, match="duplicate"):
        load_workflow(v5_root, "demo")


def test_short_name_agents_resolve(v5_root):
    """I-50: `executor: executor` loads harness/workflows/agents/executor.yaml."""
    make_node(v5_root, "a", agents={"executor": "executor", "reviewer": {"agent": "reviewer", "max_turns": 5}})
    node = load_node(v5_root, "a")
    assert node.agents["executor"].definition.deliver.submit == "artifact"
    assert node.agents["reviewer"].definition.deliver.submit == "verdict" and node.agents["reviewer"].max_turns == 5


def test_unknown_agent_name_has_file_and_line(v5_root):
    make_node(v5_root, "a", agents={"executor": "nobody", "reviewer": "reviewer"})
    with pytest.raises(ConfigError, match=r"nodes/a\.yaml:\d+: unknown agent 'nobody'.*known: executor, reviewer"):
        load_node(v5_root, "a")


def test_old_role_form_is_rejected(v5_root):
    make_node(v5_root, "a", agents={"executor": {"role": "executor"}, "reviewer": "reviewer"})
    with pytest.raises(ConfigError, match=r"nodes/a\.yaml:\d+: agent 'executor': 'role' was replaced"):
        load_node(v5_root, "a")


INLINE_EXEC = {"prompt": "按 <plan> 写段落。", "access": {"read": {"knowledge": False}},
               "deliver": {"submit": "artifact", "spec": "paragraph", "max_turns": 7}}


def test_inline_agent_in_node(v5_root):
    """I-50: an agent object with prompt/deliver is an inline agent; other keys are node overrides."""
    make_node(v5_root, "a", produces=[{"path": "text"}],
              agents={"executor": {**INLINE_EXEC, "tools": {"mcp": ["control_openlca"]}}, "reviewer": "reviewer"})
    node = load_node(v5_root, "a")
    ex = node.agents["executor"]
    assert ex.agent == "" and ex.definition.prompt.startswith("按") and ex.definition.deliver.max_turns == 7
    assert ex.definition.access.read == {"knowledge": False} and ex.tools.mcp == ["control_openlca"]
    assert node.produces[0].spec == "paragraph"  # default spec from the inline deliver


def test_bad_inline_agent_names_file_and_line(v5_root):
    make_node(v5_root, "a", agents={"executor": {"prompt": "x"}, "reviewer": "reviewer"})
    with pytest.raises(ConfigError, match=r"nodes/a\.yaml:\d+: inline agent 'executor' needs 'prompt' and 'deliver'"):
        load_node(v5_root, "a")


def test_orchestration_mixes_names_and_inline_nodes(v5_root):
    make_node(v5_root, "a", produces=[{"spec": "paragraph", "path": "text"}])
    inline = {"id": "b", "requires": ["text"], "produces": [{"spec": "summary", "path": "sum"}],
              "agents": {"executor": "executor", "reviewer": {**INLINE_EXEC, "deliver": {"submit": "verdict"}}},
              "flow": EXEC_REVIEW_FLOW}
    write_yaml(v5_root / "harness/workflows/orchestrations/mix.yaml", {"nodes": ["a", inline]})
    wf, nodes = load_workflow(v5_root, "mix")
    assert wf.nodes == ["a", "b"] and [n.id for n in nodes] == ["a", "b"]
    assert nodes[1].agents["reviewer"].definition.deliver.submit == "verdict"


def test_inline_node_errors(v5_root):
    write_yaml(v5_root / "harness/workflows/orchestrations/bad.yaml", {"nodes": [{"title": "no id"}]})
    with pytest.raises(ConfigError, match=r"orchestrations/bad\.yaml:\d+: inline node #1 needs an 'id'"):
        load_workflow(v5_root, "bad")
    write_yaml(v5_root / "harness/workflows/orchestrations/bad2.yaml", {"nodes": ["ghost"]})
    with pytest.raises(ConfigError, match=r"orchestrations/bad2\.yaml:\d+: unknown node 'ghost'"):
        load_workflow(v5_root, "bad2")


def test_node_override_does_not_touch_template(v5_root):
    """DESIGN §九: {agent: executor, max_turns, tools} applies to that node only."""
    from backend.v5.config import load_agent_def

    before = load_agent_def(v5_root, "executor").model_dump()
    tpl_text = (v5_root / "harness/workflows/agents/executor.yaml").read_text(encoding="utf-8")
    make_node(v5_root, "a", agents={"executor": {"agent": "executor", "max_turns": 3, "tools": {"mcp": ["control_openlca"]},
                                                 "access": {"read": {"knowledge": False}}}, "reviewer": "reviewer"})
    make_node(v5_root, "b", agents={"executor": "executor", "reviewer": "reviewer"})
    a, b = load_node(v5_root, "a"), load_node(v5_root, "b")
    assert a.agents["executor"].max_turns == 3 and b.agents["executor"].max_turns is None
    assert b.agents["executor"].tools.mcp == [] and b.agents["executor"].access.read == {}
    assert a.agents["executor"].definition.model_dump() == before == b.agents["executor"].definition.model_dump()
    assert a.agents["executor"].definition is not b.agents["executor"].definition
    assert (v5_root / "harness/workflows/agents/executor.yaml").read_text(encoding="utf-8") == tpl_text
