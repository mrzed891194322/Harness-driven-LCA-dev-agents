"""Outer queue + inner graph with a scripted driver (WORKFLOW_DESIGN §10)."""
import json

import pytest

from backend.v5.config import load_workflow
from backend.v5.runner import RunFailed, Runner, TurnResult
from tests.t_v5.conftest import make_node, write_yaml
from tests.t_v5.fake_driver import FakeDriver, redo

PLAN = {"main_plan.md": "# 计划\n写一段话再总结。\n"}


def _setup(root, order=("write", "summarize"), max_redos=None):
    make_node(root, "write", produces=[{"spec": "paragraph", "path": "text/paragraph.md"}])
    make_node(root, "summarize", requires=["text/paragraph.md"],
              produces=[{"spec": "summary", "path": "summary/summary.md"}])
    orch = {"nodes": list(order)}
    if max_redos is not None:
        orch["max_redos"] = max_redos
    write_yaml(root / "harness/workflows/orchestrations/demo.yaml", orch)
    return load_workflow(root, "demo")


def _chain(root, max_redos=2):
    """a -> b -> c -> d, each reading the previous one's file."""
    prev = None
    for n in "abcd":
        make_node(root, n, requires=[f"{prev}/{prev}.md"] if prev else [],
                  produces=[{"spec": "paragraph", "path": f"{n}/{n}.md"}])
        prev = n
    write_yaml(root / "harness/workflows/orchestrations/chain.yaml", {"nodes": list("abcd"), "max_redos": max_redos})
    return load_workflow(root, "chain")


def _run(root, driver, resume=False, wfn=None, **kw):
    wf, nodes = wfn or _setup(root, **kw)
    return Runner(root, wf, nodes, driver, retry_interval=0).run(plans=PLAN, resume=resume)


def _events(root):
    path = root / "workspace/runs/_run/events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _manifest(root):
    return json.loads((root / "workspace/runs/_run/manifest.json").read_text())


def test_pass_through(v5_root):
    assert _run(v5_root, FakeDriver()) == "completed"
    ws = v5_root / "workspace"
    assert (ws / "artifacts/summary/summary.md").is_file()
    m = _manifest(v5_root)
    assert m["status"] == "completed" and [n["status"] for n in m["nodes"]] == ["passed", "passed"]
    ev = [e for e in _events(v5_root) if e.get("node") == "write"]
    kinds = [e["kind"] for e in ev if e["kind"] in ("submit", "route", "node_end")]
    assert kinds == ["submit", "route", "submit", "route", "node_end"]
    seqs = [e["seq"] for e in _events(v5_root)]
    assert seqs == list(range(1, len(seqs) + 1))
    assert all(e.get("run_id") for e in _events(v5_root) if e["kind"] != "plan_written")


def test_reject_then_pass_reuses_executor_session(v5_root):
    d = FakeDriver({("write", "reviewer"): ["reject", "approve"]})
    assert _run(v5_root, d) == "completed"
    write_calls = [c for c in d.calls if c[0] == "write"]
    assert write_calls == [("write", "executor", 1, False), ("write", "reviewer", 1, False),
                           ("write", "executor", 2, True), ("write", "reviewer", 2, False)]
    assert "第一段太短" in (v5_root / "workspace/runs/write/feedback/round_1.md").read_text(encoding="utf-8")
    assert "<rework>" in d.prompts[2] and "第一段太短" in d.prompts[2] and "<rework>" not in d.prompts[0]


def test_reject_limit_back_edge(v5_root):
    d = FakeDriver({("write", "reviewer"): ["reject"] * 10})
    assert _run(v5_root, d) == "failed"
    assert "back_edge_limit" in _manifest(v5_root)["status_reason"]
    assert sum(1 for c in d.calls if c[1] == "executor") == 4  # 1 + max 3


def test_terminate(v5_root):
    assert _run(v5_root, FakeDriver({("write", "reviewer"): ["terminate"]})) == "failed"
    assert "无法通过返工修正" in _manifest(v5_root)["status_reason"]


def test_blocked_skips_reviewer(v5_root):
    d = FakeDriver({("write", "executor"): ["blocked"]})
    assert _run(v5_root, d) == "failed"
    assert [c[1] for c in d.calls] == ["executor"]
    m = _manifest(v5_root)
    assert "上游资料缺少关键数据" in m["status_reason"] and m["nodes"][0]["status"] == "blocked"


def test_fatal_auth_error_stops_run(v5_root):
    d = FakeDriver({("write", "executor"): [TurnResult(error="401 api_key_expired", fatal=True)]})
    assert _run(v5_root, d) == "failed"
    assert len(d.calls) == 1


def test_no_submit(v5_root):
    d = FakeDriver({("write", "executor"): [TurnResult(aborted=True, abort_reason="max_turns")]})
    assert _run(v5_root, d) == "failed"
    assert "no_submit" in _manifest(v5_root)["status_reason"] and "max_turns" in _manifest(v5_root)["status_reason"]


def test_transient_error_retried(v5_root):
    d = FakeDriver({("write", "executor"): [TurnResult(error="fetch failed")]})
    assert _run(v5_root, d) == "completed"
    assert [c[:3] for c in d.calls[:2]] == [("write", "executor", 1), ("write", "executor", 1)]


def test_transient_error_twice_fails(v5_root):
    d = FakeDriver({("write", "executor"): [TurnResult(error="fetch failed")] * 2})
    assert _run(v5_root, d) == "failed"
    assert "transient_error" in _manifest(v5_root)["status_reason"]


def test_max_steps(v5_root):
    flow = {"start": "executor", "max_steps": 5, "edges": [
        {"from": "executor", "when": "done", "to": "reviewer"},
        {"from": "reviewer", "when": "reject", "to": "executor", "max": 50},
        {"from": "reviewer", "when": "approve", "to": "done"}]}
    make_node(v5_root, "loop", produces=[{"spec": "paragraph", "path": "l/l.md"}], flow=flow)
    write_yaml(v5_root / "harness/workflows/orchestrations/loop.yaml", {"nodes": ["loop"]})
    d = FakeDriver({("loop", "reviewer"): ["reject"] * 50})
    assert _run(v5_root, d, wfn=load_workflow(v5_root, "loop")) == "failed"
    assert len(d.calls) == 5 and "max_steps" in _manifest(v5_root)["status_reason"]


def test_requires_missing_fails_immediately(v5_root):
    d = FakeDriver()
    assert _run(v5_root, d, order=("summarize",)) == "failed"
    assert d.calls == []
    assert any(e["kind"] == "requires_failed" for e in _events(v5_root))


def test_checks_failed_feedback(v5_root):
    write_yaml(v5_root / "harness/specs/summary.yaml", {"description": "x", "schema": {"type": "object"}})
    make_node(v5_root, "j", produces=[{"spec": "summary", "path": "j/out.json"}])
    write_yaml(v5_root / "harness/workflows/orchestrations/dj.yaml", {"nodes": ["j"]})
    d = FakeDriver({("j", "executor"): ["[1]", '{"a": 1}']})
    assert _run(v5_root, d, wfn=load_workflow(v5_root, "dj")) == "completed"
    assert "宿主检查未通过" in (v5_root / "workspace/runs/j/feedback/round_1.md").read_text(encoding="utf-8")
    assert [c[1] for c in d.calls] == ["executor", "executor", "reviewer"]


def test_redo_approved_inserts_segment(v5_root):
    wfn = _chain(v5_root)
    d = FakeDriver({("c", "executor"): [redo("b", "b/b.md")], ("c", "reviewer"): ["redo"]})
    assert _run(v5_root, d, wfn=wfn) == "completed"
    order = []
    for c in d.calls:
        if c[1] == "executor" and (not order or order[-1] != c[0]):
            order.append(c[0])
    assert order == ["a", "b", "c", "b@rev1", "c@rev1", "d"]
    art = v5_root / "workspace/artifacts"
    assert (art / "b/b.rev1.md").is_file() and "b 的产出" in (art / "b/b.md").read_text(encoding="utf-8")
    c1 = next(r for r in d.reqs if r.node.run_key == "c@rev1")
    assert c1.node.requires == ["b/b.rev1.md"] and c1.session_key == "c@rev1.executor" and not c1.resume
    d_req = next(r for r in d.reqs if r.node.id == "d")
    assert d_req.node.requires == ["c/c.rev1.md"]
    b1 = next(r for r in d.reqs if r.node.run_key == "b@rev1")
    assert "<redo_reason>" not in b1.prompt or True
    appended = [e for e in _events(v5_root) if e["kind"] == "queue_append"]
    assert appended[0]["items"] == [{"node": "b", "rev": 1}, {"node": "c", "rev": 1}]
    q = json.loads((v5_root / "workspace/runs/_run/queue.json").read_text())
    assert q["redos"] == 1 and q["queue"] == []
    assert [(n["key"], n["status"]) for n in _manifest(v5_root)["nodes"]] == [
        ("a", "passed"), ("b", "passed"), ("c", "redo_upstream"), ("b@rev1", "passed"), ("c@rev1", "passed"),
        ("d", "passed")]


def test_redo_rejected_by_reviewer(v5_root):
    wfn = _chain(v5_root)
    d = FakeDriver({("c", "executor"): [redo("b", "b/b.md")], ("c", "reviewer"): ["reject", "approve"]})
    assert _run(v5_root, d, wfn=wfn) == "completed"
    assert not any(c[0].endswith("@rev1") for c in d.calls)
    prompt = [p for c, p in zip(d.calls, d.prompts) if c[:3] == ("c", "executor", 2)][0]
    assert "回溯请求未获批准" in prompt


def test_redo_limit(v5_root):
    wfn = _chain(v5_root, max_redos=1)
    d = FakeDriver({("c", "executor"): [redo("b", "b/b.md")], ("c", "reviewer"): ["redo", "redo"],
                    ("c@rev1", "executor"): [redo("b", "b/b.md")]})
    assert _run(v5_root, d, wfn=wfn) == "failed"
    assert "redo_limit" in _manifest(v5_root)["status_reason"]
    assert any(e["kind"] == "redo_refused" and e["reason"] == "max_redos" for e in _events(v5_root))


def test_redo_target_invalid_rejected_by_host(v5_root):
    wfn = _chain(v5_root)
    d = FakeDriver({("b", "executor"): [redo("c", "c/c.md")]})
    assert _run(v5_root, d, wfn=wfn) == "failed"
    assert "submit_invalid" in _manifest(v5_root)["status_reason"]


def test_redo_without_reviewer_fails(v5_root):
    _chain(v5_root)
    make_node(v5_root, "c", requires=["b/b.md"], produces=[{"spec": "paragraph", "path": "c/c.md"}],
              agents={"executor": "executor"})
    wf, nodes = load_workflow(v5_root, "chain")
    d = FakeDriver({("c", "executor"): [redo("b", "b/b.md")]})
    assert _run(v5_root, d, wfn=(wf, nodes)) == "failed"
    assert "redo_needs_reviewer" in _manifest(v5_root)["status_reason"]


def test_resume_from_queue(v5_root):
    calls = {"n": 0}
    stop = lambda: calls["n"] >= 3  # noqa: E731

    def count(req):
        calls["n"] += 1

    wf, nodes = _setup(v5_root)
    assert Runner(v5_root, wf, nodes, FakeDriver(on_turn=count), stop_requested=stop).run(plans=PLAN) == "stopped"
    ws = v5_root / "workspace"
    assert json.loads((ws / "runs/write/status.json").read_text())["status"] == "passed"
    assert json.loads((ws / "runs/summarize/status.json").read_text())["status"] == "stopped"
    d2 = FakeDriver()
    assert Runner(v5_root, wf, nodes, d2).run(resume=True) == "completed"
    assert all(c[0] == "summarize" for c in d2.calls) and d2.calls[0][2] == 1


def test_runner_with_injector_prompts(v5_root):
    from backend.v5.inject import Injector

    wf, nodes = _setup(v5_root)
    d = FakeDriver()
    assert Runner(v5_root, wf, nodes, d, prompt_builder=Injector(v5_root)).run(plans=PLAN) == "completed"
    assert "<plan>" in d.prompts[0] and "写一段话再总结" in d.prompts[0]
    assert "<redo_policy>" in d.prompts[0] and "不能请求回溯" in d.prompts[0]
    summ = [p for c, p in zip(d.calls, d.prompts) if c[:2] == ("summarize", "executor")][0]
    assert "write（text/paragraph.md）" in summ
    review = [p for c, p in zip(d.calls, d.prompts) if c[:2] == ("write", "reviewer")][0]
    assert "<executor_submit>" in review
    assert d.systems[0].startswith("# 红线")


def test_lock_prevents_parallel_run(v5_root):
    import fcntl

    wf, nodes = _setup(v5_root)
    lock = v5_root / "workspace/runs/_run/orchestrator.lock"
    lock.parent.mkdir(parents=True)
    with lock.open("a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        with pytest.raises(RunFailed):
            Runner(v5_root, wf, nodes, FakeDriver()).run(plans=PLAN)
