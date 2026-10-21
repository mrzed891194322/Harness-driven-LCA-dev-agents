import json

import pytest

from backend.v5.config import load_workflow
from backend.v5.runner import Runner, TurnResult
from tests.t_v5.conftest import make_node, write_yaml
from tests.t_v5.fake_driver import FakeDriver

PLAN = {"main_plan.md": "# 计划\n写一段话再总结。\n"}


def _setup(root, order=("write", "summarize")):
    make_node(root, "write", produces=[{"spec": "paragraph", "path": "text/paragraph.md"}])
    make_node(root, "summarize", requires=["text"], produces=[{"spec": "summary", "path": "summary/summary.md"}])
    write_yaml(root / "harness/workflows/demo.yaml", {"nodes": list(order)})
    return load_workflow(root, "demo")


def _run(root, driver, resume=False, **kw):
    wf, nodes = _setup(root, **kw)
    return Runner(root, wf, nodes, driver).run(plans=PLAN, resume=resume)


def _events(root):
    path = root / "workspace/runs/_run/events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_pass_through(v5_root):
    assert _run(v5_root, FakeDriver()) == "completed"
    ws = v5_root / "workspace"
    assert (ws / "artifacts/plan/main_plan.md").is_file()
    assert (ws / "artifacts/summary/summary.md").is_file()
    m = json.loads((ws / "runs/_run/manifest.json").read_text())
    assert m["status"] == "completed" and [n["status"] for n in m["nodes"]] == ["passed", "passed"]
    kinds = [e["kind"] for e in _events(v5_root)]
    for k in ("lock_acquired", "run_start", "plan_written", "node_start", "review_verdict", "node_end", "run_end"):
        assert k in kinds


def test_reject_then_pass_reuses_executor_session(v5_root):
    d = FakeDriver({("write", "reviewer"): ["reject", "pass"]})
    assert _run(v5_root, d) == "completed"
    write_calls = [c for c in d.calls if c[0] == "write"]
    assert write_calls[:4] == [("write", "executor", 1, False), ("write", "reviewer", 1, False),
                               ("write", "executor", 2, True), ("write", "reviewer", 2, False)]
    fb = v5_root / "workspace/runs/write/feedback/round_1.md"
    assert "第一段太短" in fb.read_text(encoding="utf-8")
    assert "<rework>" in d.prompts[2] and "<rework>" not in d.prompts[0]


def test_max_rounds(v5_root):
    d = FakeDriver({("write", "reviewer"): ["reject"] * 5})
    assert _run(v5_root, d) == "failed"
    m = json.loads((v5_root / "workspace/runs/_run/manifest.json").read_text())
    assert "最大轮数" in m["status_reason"]


def test_reviewer_stop(v5_root):
    assert _run(v5_root, FakeDriver({("write", "reviewer"): ["stop"]})) == "failed"


def test_fatal_auth_error_stops_run(v5_root):
    d = FakeDriver({("write", "executor"): [TurnResult(error="401 api_key_expired", fatal=True)]})
    assert _run(v5_root, d) == "failed"
    assert len(d.calls) == 1


def test_requires_missing_fails_immediately(v5_root):
    d = FakeDriver()
    assert _run(v5_root, d, order=("summarize",)) == "failed"
    assert d.calls == []
    assert any(e["kind"] == "requires_failed" for e in _events(v5_root))


def test_checks_failed_feedback(v5_root):
    write_yaml(v5_root / "harness/specs/summary.yaml", {"description": "x", "schema": {"type": "object"}})
    make_node(v5_root, "j", produces=[{"spec": "summary", "path": "j/out.json"}])
    write_yaml(v5_root / "harness/workflows/dj.yaml", {"nodes": ["j"]})
    wf, nodes = load_workflow(v5_root, "dj")
    d = FakeDriver({("j", "executor"): ["[1]", '{"a": 1}']})
    assert Runner(v5_root, wf, nodes, d).run(plans=PLAN) == "completed"
    fb = (v5_root / "workspace/runs/j/feedback/round_1.md").read_text(encoding="utf-8")
    assert "宿主检查未通过" in fb


def test_resume_skips_passed_and_reruns_interrupted(v5_root):
    calls = {"n": 0}
    stop = lambda: calls["n"] >= 3  # noqa: E731

    def count(req):
        calls["n"] += 1

    wf, nodes = _setup(v5_root)
    d1 = FakeDriver(on_turn=count)
    assert Runner(v5_root, wf, nodes, d1, stop_requested=stop).run(plans=PLAN) == "stopped"
    ws = v5_root / "workspace"
    assert json.loads((ws / "runs/write/status.json").read_text())["status"] == "passed"
    assert json.loads((ws / "runs/summarize/status.json").read_text())["status"] == "stopped"
    d2 = FakeDriver()
    assert Runner(v5_root, wf, nodes, d2).run(resume=True) == "completed"
    assert all(c[0] == "summarize" for c in d2.calls)
    assert d2.calls[0][2] == 1


def test_runner_with_injector_prompts(v5_root):
    from backend.v5.inject import Injector

    wf, nodes = _setup(v5_root)
    d = FakeDriver()
    assert Runner(v5_root, wf, nodes, d, prompt_builder=Injector(v5_root)).run(plans=PLAN) == "completed"
    assert "<plan>" in d.prompts[0] and "写一段话再总结" in d.prompts[0]
    assert d.systems[0].startswith("# 红线")


def test_lock_prevents_parallel_run(v5_root):
    import fcntl

    wf, nodes = _setup(v5_root)
    lock = v5_root / "workspace/runs/_run/orchestrator.lock"
    lock.parent.mkdir(parents=True)
    with lock.open("a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        from backend.v5.runner import RunFailed

        with pytest.raises(RunFailed):
            Runner(v5_root, wf, nodes, FakeDriver()).run(plans=PLAN)
