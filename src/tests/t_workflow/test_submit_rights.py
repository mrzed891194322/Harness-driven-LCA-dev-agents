"""r20a: write vs submit orthogonality + inject_when global rules + bom tier matrix."""
from __future__ import annotations

from backend.workflow.config import default_flow, load_workflow
from backend.workflow.inject import Injector
from backend.workflow.pi_driver import effective_file_tools
from tests.t_workflow.conftest import REPO


def test_trio_default_flow_starts_at_orchestrator_hub():
    flow = default_flow({"orchestrator": 1, "executor": 1, "reviewer": 1})
    assert flow["start"] == "orchestrator"
    whens = {(e["from"], e.get("when")) for e in flow["edges"]}
    assert ("orchestrator", "assign_executor") in whens
    assert ("orchestrator", "assign_reviewer") in whens
    assert ("executor", None) in whens


def test_bom_tier_tools_and_submit_prompt_matrix():
    inj = Injector(REPO)
    _, n01 = load_workflow(REPO, "bom-extract-01")
    _, n02 = load_workflow(REPO, "bom-extract-02")
    _, n03 = load_workflow(REPO, "bom-extract-03")
    node = n03[0]
    for thin in (n01[0], n02[0]):
        agent = "executor"
        assert thin.is_writer(agent) and thin.is_primary(agent)
        assert "write" in effective_file_tools(thin, agent)
        sys = inj.system(thin, agent)
        assert "交卷（写作者）" in sys or "写完 claims" in sys
        report = inj.build_session_injection_report(thin, agent, attempt=1, user_prompt="u", run_id="m")
        ft = report["sections"]["tools"]["file_tools"]
        assert "write" in ft and "edit" in ft and "submit" in ft

    assert not node.is_writer("orchestrator") and node.is_primary("orchestrator")
    assert node.is_writer("executor") and not node.is_primary("executor")
    assert "submit" not in effective_file_tools(node, "executor")
    assert "write" in effective_file_tools(node, "executor")
    assert effective_file_tools(node, "orchestrator") == ["read", "ls", "grep", "find"]
    assert "write" in effective_file_tools(node, "reviewer")

    ex_sys = inj.system(node, "executor")
    assert "交卷（写作者）" not in ex_sys
    assert "不要调用 submit" in ex_sys or "无交卷" in ex_sys

    orch_sys = inj.system(node, "orchestrator")
    assert "交卷（主 agent）" in orch_sys
    assert "assign_executor" in orch_sys

    ex_report = inj.build_session_injection_report(node, "executor", attempt=1, user_prompt="u", run_id="m")
    assert "submit" not in ex_report["sections"]["tools"]["file_tools"]
    orch_report = inj.build_session_injection_report(node, "orchestrator", attempt=1, user_prompt="u", run_id="m")
    assert "submit" in orch_report["sections"]["tools"]["file_tools"]
    assert "write" not in orch_report["sections"]["tools"]["file_tools"]

    # 01 snapshot unchanged shape
    r01 = inj.build_session_injection_report(n01[0], "executor", attempt=1, user_prompt="u", run_id="m")
    assert "submit" in r01["sections"]["tools"]["file_tools"]
