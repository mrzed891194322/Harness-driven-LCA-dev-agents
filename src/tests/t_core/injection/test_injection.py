"""Injection manifest: intended vs effective diff, redaction, strict mode, self-check."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

from backend.core.agents import injection
from backend.core.contracts.session_launch_spec import (
    KnowledgeBinding,
    ModelProfile,
    PermissionPolicy,
    SessionLaunchSpec,
    SystemSection,
)

REPO = Path(__file__).resolve().parents[4]
FAKE_SECRET = "sk-FAKEplantedSECRETvalue0123456789"
FAKE_TOKEN = "fake-spec-mcp-token-ABCDEF0123456789"
FAKE_ENV_KEY = "planted-env-api-key-XYZ0123456789"


def _launch(tmp: Path) -> SessionLaunchSpec:
    spec = SessionLaunchSpec(
        run_id="r1", stage_id="03-x", assignment_id="a", role="executor", attempt=2,
        session_key="a", execution_id="e", bundle_hash="b", input_snapshot_hash="i",
        model_profile=ModelProfile(profile_id="p", provider="prov", model_id="m1"),
        system_sections=[
            SystemSection(id="spec_context", content="# spec\n{}", source_hash="h1"),
            SystemSection(id="assignment_prompt", content="# 通用\nA\n\n# 规则 r\nB\n", source_hash="h2"),
        ],
        turn_context={}, knowledge_bindings=[KnowledgeBinding(id="k", root_path="/k", content_hash="c")],
        resource_bindings={"project_root": str(tmp)},
        mcp_bindings={"spec_mcp": {"command": "py", "args": [], "env": {"SPEC_MCP_TOKEN": FAKE_TOKEN},
                                   "timeout_ms": 1000, "exposure": "direct"}},
        permission_policy=PermissionPolicy(allowed_tools=["read", "mcp__spec_mcp__*"],
                                           allowed_read_globs=[], allowed_write_globs=[]),
        session_storage={"agent_dir": str(tmp / "ag"), "session_file": str(tmp / "s.jsonl")},
    )
    spec.prompt_segments = [
        {"id": "runtime_protocol", "kind": "builtin", "source": "x.py", "origin": "builtin", "content": "# 通用\nA"},
        {"id": "rule:r", "kind": "rule", "source": "harness/rules/r.md", "origin": "user", "file_sha256": "f", "content": "# 规则 r\nB"},
    ]
    spec.spec_view = {"spec_id": "03-x"}
    return spec


def _effective(launch: SessionLaunchSpec, **over) -> dict:
    prompt = injection.runtime_system_prompt(launch)
    tools = [f"mcp__spec_mcp__{t}" for t in injection.SPEC_MCP_TOOLS] + ["read"]
    eff = {
        "captured": True, "system_prompt": "SDK header\n" + prompt + "\nSDK footer",
        "system_prompt_hash": "x", "model": {"provider": "prov", "model_id": "m1"},
        "active_tool_names": tools, "tools": [{"name": t} for t in tools],
        "mcp_servers": {"spec_mcp": {"tools": tools[:4], "exposures": ["direct"]}},
        "skills": [], "extensions": ["<inline>"], "extension_errors": [],
        "guard_hook_mounted": True, "first_request_hook": True,
    }
    eff.update(over)
    return eff


def _levels(result):
    return {i["item"]: i["level"] for i in result["items"]}


def test_diff_ok_and_sdk_additions_are_not_anomalies(tmp_path):
    launch = _launch(tmp_path)
    result = injection.diff(injection.build_intended(launch), _effective(launch))
    assert result["level"] == "ok", result
    sp = next(i for i in result["items"] if i["item"] == "system_prompt")
    assert sp["kind"] == "sdk_added" and sp["added_before_chars"] > 0


def test_diff_flags_model_spec_mcp_guard_as_critical(tmp_path):
    launch = _launch(tmp_path)
    eff = _effective(launch, model={"provider": "prov", "model_id": "other"}, guard_hook_mounted=False,
                     active_tool_names=["read", "bash"], mcp_servers={})
    result = injection.diff(injection.build_intended(launch), eff)
    lv = _levels(result)
    assert result["level"] == "mismatch" and result["critical_mismatch"]
    assert lv["model"] == lv["guard_hook"] == lv["mcp:spec_mcp"] == lv["tool:mcp__spec_mcp__*"] == "mismatch"
    assert lv["tools:unplanned"] == "warn"


def test_missing_segment_and_not_captured(tmp_path):
    launch = _launch(tmp_path)
    eff = _effective(launch, system_prompt="something else")
    lv = _levels(injection.diff(injection.build_intended(launch), eff))
    assert lv["system_prompt"] == "mismatch" and lv["segment:rule:r"] == "mismatch"
    r = injection.diff(injection.build_intended(launch), {"captured": False, "reason": "mock"})
    assert r["level"] == "warn" and not r["critical_mismatch"]


def test_default_records_only_strict_raises(tmp_path, monkeypatch):
    launch = _launch(tmp_path)
    bad = injection.diff(injection.build_intended(launch), _effective(launch, guard_hook_mounted=False))
    monkeypatch.delenv(injection.STRICT_ENV, raising=False)
    injection.enforce(bad)  # default: never interrupts
    monkeypatch.setenv(injection.STRICT_ENV, "1")
    with pytest.raises(injection.InjectionMismatch):
        injection.enforce(bad)


def test_snapshots_written_and_no_planted_secret_leaks(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE_ENV_KEY)
    (tmp_path / ".local" / "run").mkdir(parents=True)
    (tmp_path / ".local" / "run" / "spec_mcp.key").write_text("signing-key-0123456789abcdef", encoding="utf-8")
    launch = _launch(tmp_path)
    launch.system_sections[1].content += f"\nleak {FAKE_SECRET} {FAKE_ENV_KEY} signing-key-0123456789abcdef\n"
    eff = _effective(launch)
    eff["payload_note"] = f"Bearer {FAKE_TOKEN} {FAKE_ENV_KEY}"
    result = injection.write_session_snapshots(tmp_path, launch, eff)
    injection.record_first_prompt(tmp_path, launch, f"first prompt {FAKE_SECRET}")
    injection.record_first_request(tmp_path, launch, {"system_prompt_found": True, "tool_names": ["read"], "bytes": 3})
    d = injection.session_snapshot_dir(tmp_path, "r1", "03-x", "executor", 2)
    assert d.name == "03-x.executor.2" and result["session"] == d.name
    for name in ("prompt.md", "spec.json", "tools.json", "permissions.json", "launch.json",
                 "injection/intended.json", "injection/effective.json", "injection/diff.json"):
        assert (d / name).is_file(), name
    blob = "".join(p.read_text(encoding="utf-8") for p in d.rglob("*") if p.is_file())
    blob += (tmp_path / ".local" / "runs" / "r1" / "events.jsonl").read_text(encoding="utf-8")
    for secret in (FAKE_SECRET, FAKE_TOKEN, FAKE_ENV_KEY, "signing-key-0123456789abcdef"):
        assert secret not in blob, secret
    launch_json = json.loads((d / "launch.json").read_text(encoding="utf-8"))
    assert launch_json["env_names"] == ["SPEC_MCP_TOKEN"]
    intended = json.loads((d / "injection" / "intended.json").read_text(encoding="utf-8"))
    assert intended["first_user_prompt"]["chars"] > 0
    seg = next(s for s in intended["segments"] if s["id"] == "rule:r")
    assert seg["origin"] == "user" and seg["source"] == "harness/rules/r.md"
    events = [json.loads(x) for x in (tmp_path / ".local/runs/r1/events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["phase"] for e in events if e["kind"] == "injection_check"] == ["create", "first_request"]
    summary = injection.run_summary(tmp_path, "r1")
    assert summary["sessions"] == 1 and summary["mismatches"] == []


def test_run_summary_lists_mismatches(tmp_path):
    launch = _launch(tmp_path)
    injection.write_session_snapshots(tmp_path, launch, _effective(launch, guard_hook_mounted=False))
    s = injection.run_summary(tmp_path, "r1")
    assert s["anomaly"] and s["mismatches"][0]["item"] == "guard_hook"
    with pytest.raises(ValueError):
        injection.snapshot_file(tmp_path, "r1", "..", "prompt.md")
    with pytest.raises(ValueError):
        injection.snapshot_file(tmp_path, "r1", "x", "../../etc/passwd")


@pytest.mark.skipif(os.name == "nt", reason="unix socket")
def test_empty_session_selfcheck_against_real_runtime(tmp_path):
    """Real pi-runtime (not mock) on a private socket: create, compare, release; no model call."""
    from backend.core.agents.injection_selfcheck import run_selfcheck
    from backend.pi_client.process import PiRuntimeClient, runtime_entry

    if shutil.which("node") is None:
        pytest.skip("node missing")
    sock = tmp_path / "rt.sock"
    env = {k: v for k, v in os.environ.items() if k not in ("PI_RUNTIME_MOCK", "PI_RUNTIME_PRIVATE")}
    proc = subprocess.Popen([*runtime_entry(REPO), "--listen", str(sock)], cwd=str(REPO), env=env,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = REPO / ".local" / "runs" / "doctor-selfcheck"
    try:
        deadline = time.monotonic() + 30
        while not sock.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        client = PiRuntimeClient(REPO, socket_file=sock, label="pytest-selfcheck")
        try:
            result = run_selfcheck(client, REPO)
        finally:
            client.close()
        assert result["ok"], json.dumps(result, ensure_ascii=False, indent=1)
        lv = _levels(result)
        assert lv["model"] == lv["guard_hook"] == lv["mcp:spec_mcp"] == "ok"
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(out, ignore_errors=True)


def test_snapshot_api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.api import app as api
    from backend.services.session_snapshots import SessionSnapshots

    launch = _launch(tmp_path)
    injection.write_session_snapshots(tmp_path, launch, _effective(launch, guard_hook_mounted=False))
    monkeypatch.setattr(api, "_snapshots", SessionSnapshots(tmp_path))
    c = TestClient(api.app)
    runs = c.get("/api/runs").json()["runs"]
    assert runs[0]["run_id"] == "r1" and runs[0]["anomaly"]
    detail = c.get("/api/runs/r1/sessions").json()
    assert detail["sessions"][0]["session"] == "03-x.executor.2"
    inj = c.get("/api/runs/r1/sessions/03-x.executor.2/injection").json()
    assert inj["diff"]["level"] == "mismatch" and inj["intended"]["model"]["model_id"] == "m1"
    assert c.get("/api/runs/r1/sessions/03-x.executor.2/file", params={"name": "prompt.md"}).json()["text"]
    assert c.get("/api/runs/r1/sessions/03-x.executor.2/file", params={"name": "../x"}).status_code == 400
    assert c.get("/api/runs/r1/sessions/03-x.executor.2/file", params={"name": "launch.json", "download": True}).status_code == 200
