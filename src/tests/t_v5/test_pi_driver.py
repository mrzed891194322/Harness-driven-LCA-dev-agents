"""PiDriver against a fake runtime (no pi process, temp project only)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from backend.core.contracts.session_launch_spec import ModelProfile
from backend.v5.config import load_node
from backend.v5.pi_driver import PiDriver, is_auth_error, is_transient_error
from backend.v5.runner import TurnRequest
from tests.t_v5.conftest import REPO, make_node, write_yaml

MODEL = ModelProfile(profile_id="p", provider="x", model_id="m", display_name="m")


class FakeRuntime:
    def __init__(self, submit=None, result=None, raise_on=None):
        self.calls: list[tuple[str, dict]] = []
        self.submit = submit
        self.result = result or {"status": "ok", "text": "done", "outcome": {"stop_reason": "stop"}}
        self.raise_on = raise_on

    def request(self, method, params=None, *, timeout=0):
        self.calls.append((method, params or {}))
        if method == self.raise_on:
            raise RuntimeError("401 api_key_expired")
        if method == "session.run_turn" and self.submit is not None:
            spec = next(p["launch_spec"] for m, p in reversed(self.calls) if "launch_spec" in p)
            f = Path(spec["mcp_bindings"]["submit"]["env"]["V5_SUBMIT_FILE"])
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(self.submit), encoding="utf-8")
        return self.result


def _setup(root: Path, **agent_extra):
    (root / "harness/tools/mcp/control_openlca").mkdir(parents=True)
    write_yaml(root / "harness/tools/mcp/control_openlca/v5.yaml", {
        "command": "uv", "args": ["run", "python", "harness/tools/mcp/control_openlca/main.py"],
        "tool_timeout_sec": 10, "deny_tools": ["cleanup_output"],
        "readonly_tools": ["health_check"], "write_tools": ["import_lci"]})
    make_node(root, "n1", produces=[{"spec": "paragraph", "path": "out/p.md"}], agents={
        "executor": {"role": "executor", "tools": {"mcp": ["control_openlca"]}, "thinking": "high"},
        "reviewer": {"role": "reviewer", "tools": {"mcp": ["control_openlca"]}}})
    return load_node(root, "n1")


def _req(root, node, role="executor", rnd=1, resume=False):
    return TurnRequest(node=node, role=role, round=rnd, prompt="做事", workspace=root / "workspace",
                       run_id="run12345", session_key=f"n1-{role}", resume=resume, extra={"system": "SYS"})


def test_launch_spec_tools_scopes_and_mcp(v5_root):
    node = _setup(v5_root)
    d = PiDriver(v5_root, MODEL, runtime=FakeRuntime())
    spec, submit = d.launch_spec(_req(v5_root, node))
    pol = spec.permission_policy
    assert "bash" not in pol.allowed_tools and pol.deny_shell
    assert "mcp__submit__submit" in pol.allowed_tools
    assert "mcp__control_openlca__import_lci" in pol.allowed_tools
    assert not any("cleanup_output" in t for t in pol.allowed_tools)
    assert spec.mcp_bindings["control_openlca"]["command"] == sys.executable
    assert spec.mcp_bindings["control_openlca"]["exposure"] == "direct"
    assert any(g.endswith("artifacts/out/**") for g in pol.allowed_write_globs)
    assert any("artifacts/plan" in g for g in pol.denied_write_globs)
    assert spec.system_sections[0].content == "SYS"
    assert spec.model_profile.parameters["thinking"] == "high"
    assert submit.name == "submit.json"
    rspec, _ = d.launch_spec(_req(v5_root, node, role="reviewer"))
    rt = rspec.permission_policy.allowed_tools
    assert "edit" not in rt and "mcp__control_openlca__health_check" in rt
    assert "mcp__control_openlca__import_lci" not in rt


def test_turn_reads_submit_and_reuses_live_session(v5_root):
    node = _setup(v5_root)
    rt = FakeRuntime(submit={"status": "ok", "summary": "s"})
    d = PiDriver(v5_root, MODEL, runtime=rt)
    res = d.run_turn(_req(v5_root, node))
    assert res.submit["status"] == "ok" and not res.error and not res.fatal
    res2 = d.run_turn(_req(v5_root, node, rnd=2, resume=True))
    assert res2.submit["status"] == "ok"
    assert (v5_root / "workspace/runs/n1/executor/submit_round_2.json").is_file()
    methods = [m for m, _ in rt.calls]
    assert methods.count("session.create") == 1 and methods.count("session.run_turn") == 2


def test_resume_restores_tools_from_new_launch_spec(v5_root):
    """After a host restart the session file exists but is not live: resume with full tools."""
    node = _setup(v5_root)
    d = PiDriver(v5_root, MODEL, runtime=FakeRuntime())
    spec, _ = d.launch_spec(_req(v5_root, node, resume=True))
    sf = Path(spec.session_storage["session_file"])
    sf.parent.mkdir(parents=True, exist_ok=True)
    sf.write_text("{}\n")
    rt = FakeRuntime(submit={"status": "ok", "summary": "s"})
    d2 = PiDriver(v5_root, MODEL, runtime=rt)
    d2.run_turn(_req(v5_root, node, resume=True))
    method, params = rt.calls[0]
    assert method == "session.resume"
    tools = params["launch_spec"]["permission_policy"]["allowed_tools"]
    assert "mcp__submit__submit" in tools and "mcp__control_openlca__import_lci" in tools
    assert set(params["launch_spec"]["mcp_bindings"]) == {"submit", "control_openlca"}


def test_auth_error_is_fatal_and_aborted_is_reported(v5_root):
    node = _setup(v5_root)
    res = PiDriver(v5_root, MODEL, runtime=FakeRuntime(raise_on="session.create")).run_turn(_req(v5_root, node))
    assert res.fatal and "401" in res.error
    rt = FakeRuntime(result={"status": "ok", "outcome": {"stop_reason": "error",
                                                         "error_message": "401 Unauthorized"}})
    assert PiDriver(v5_root, MODEL, runtime=rt).run_turn(_req(v5_root, node)).fatal
    rt = FakeRuntime(result={"status": "ok", "outcome": {"stop_reason": "aborted"}})
    res = PiDriver(v5_root, MODEL, runtime=rt).run_turn(_req(v5_root, node))
    assert res.aborted and res.submit is None and not res.fatal
    assert is_auth_error("api_key_expired") and not is_auth_error("timeout")


def test_preflight(v5_root):
    ok = PiDriver(v5_root, MODEL, runtime=FakeRuntime()).preflight(v5_root / "workspace")
    assert ok is None
    bad = PiDriver(v5_root, MODEL, runtime=FakeRuntime(raise_on="session.run_turn"))
    assert "401" in bad.preflight(v5_root / "workspace")
    log = (v5_root / "workspace/runs/_run/events.jsonl").read_text()
    assert '"model_preflight"' in log


def test_preflight_retries_transient_errors_only(v5_root):
    class Flaky(FakeRuntime):
        def __init__(self, fails):
            super().__init__()
            self.fails = fails
            self.turns = 0

        def request(self, method, params=None, *, timeout=0):
            if method == "session.run_turn":
                self.turns += 1
                if self.turns <= self.fails:
                    raise RuntimeError("Connection error.")
            return super().request(method, params, timeout=timeout)

    waits = []
    d = PiDriver(v5_root, MODEL, runtime=Flaky(2))
    d._sleep = waits.append
    assert d.preflight(v5_root / "workspace") is None
    assert waits == [10, 30]
    d = PiDriver(v5_root, MODEL, runtime=Flaky(5))
    d._sleep = lambda _s: None
    assert "Connection error" in d.preflight(v5_root / "workspace")
    d = PiDriver(v5_root, MODEL, runtime=FakeRuntime(raise_on="session.run_turn"))  # 401: no retry
    d._sleep = lambda _s: (_ for _ in ()).throw(AssertionError("auth errors must not retry"))
    assert "401" in d.preflight(v5_root / "workspace")
    assert is_transient_error("fetch failed") and not is_transient_error("401 Unauthorized")


def test_submit_mcp_lists_role_specific_tool(tmp_path):
    script = REPO / "harness/tools/mcp/submit/main.py"
    code = ("import asyncio,runpy,sys;sys.argv=['x'];"
            "g=runpy.run_path(sys.argv[1] if False else %r, run_name='m');"
            "r=asyncio.run(g['mcp'].call_tool('submit', %s));print('OK')")
    for role, args in (("executor", {"status": "ok", "summary": "s"}),
                       ("reviewer", {"verdict": "reject", "feedback": "f"})):
        out = tmp_path / f"{role}.json"
        env = {**os.environ, "V5_SUBMIT_FILE": str(out), "V5_ROLE": role}
        p = subprocess.run([sys.executable, "-c", code % (str(script), repr(args))],
                           env=env, capture_output=True, text=True, timeout=60)
        assert p.returncode == 0, p.stderr
        assert json.loads(out.read_text())["role"] == role


def test_mcp_not_ready_is_its_own_reason(v5_root):
    node = _setup(v5_root)
    rt = FakeRuntime(result={"status": "error", "message": "MCP 服务未就绪（90 秒内未注册任何工具）：submit"})
    res = PiDriver(v5_root, MODEL, runtime=rt).run_turn(_req(v5_root, node))
    assert res.submit is None and res.abort_reason == "mcp_not_ready" and not res.fatal


class StreamingRuntime(FakeRuntime):
    """Streams a model_retry entry during run_turn, like pi-runtime's turn.event, then reports it again in the log."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.handlers = []
        self.log_at_stream = None

    def add_event_handler(self, h):
        self.handlers.append(h)

    def remove_event_handler(self, h):
        self.handlers.remove(h)

    def request(self, method, params=None, *, timeout=0):
        if method == "session.run_turn":
            key = params["session_key"]
            for h in list(self.handlers):
                h("turn.event", {"session_key": key, "kind": "settle", "settle_kind": "model_retry",
                                 "detail": "1/3 after 10s: 503", "ts": "T1"})
            self.log_at_stream = self.events_file.read_text() if self.events_file.is_file() else ""
            self.result = {**self.result, "message": "503 Service Unavailable",
                           "settle": {"log": [{"ts": "T1", "kind": "model_retry", "detail": "1/3 after 10s: 503"}],
                                      "model_errors": 1}}
        return super().request(method, params, timeout=timeout)


def test_model_retry_written_live_once_and_error_cleared_on_submit(v5_root):
    """I-31: model_retry reaches the event log while the turn runs, not at settle, and only once.
    I-32: a turn that recovered and submitted has no error."""
    node = _setup(v5_root)
    rt = StreamingRuntime(submit={"role": "executor", "status": "ok", "summary": "s"})
    rt.events_file = v5_root / "workspace/runs/_run/events.jsonl"
    res = PiDriver(v5_root, MODEL, runtime=rt).run_turn(_req(v5_root, node))
    assert '"model_retry"' in rt.log_at_stream
    log = rt.events_file.read_text()
    assert log.count('"model_retry"') == 1
    assert res.submit is not None and res.error == ""
    assert rt.handlers == []
