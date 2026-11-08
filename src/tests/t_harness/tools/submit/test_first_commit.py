"""Real submit validation and atomic publication; isolated files, no MCP process."""
import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


@pytest.fixture
def submit_module(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[5] / "harness/tools/mcp/submit/main.py"
    spec = importlib.util.spec_from_file_location("submit_boundary_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = tmp_path / "submit.json"
    monkeypatch.setenv("WORKFLOW_SUBMIT_FILE", str(target))
    monkeypatch.setenv("WORKFLOW_SUBMIT_CONTEXT", str(tmp_path / "context.json"))
    monkeypatch.setenv("WORKFLOW_REJECTIONS_FILE", str(tmp_path / "rejected.jsonl"))
    module.KIND = "artifact"
    return module, target


def test_first_accept_wins_with_concurrent_alternating_payloads(submit_module):
    m, target = submit_module
    payloads = [{"status": "assign_executor" if i % 2 else "assign_reviewer", "summary": str(i)} for i in range(40)]
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(m._accept, payloads))
    winners = [i for i, r in enumerate(results) if r["accepted"]]
    assert len(winners) == 1
    stored = json.loads(target.read_text())
    assert stored["summary"] == payloads[winners[0]]["summary"]
    assert all(r.get("already_submitted") for i, r in enumerate(results) if i not in winners)
    assert not list(target.parent.glob(".submit-*"))
    target.rename(target.with_name("attempt_1.json"))
    assert m._accept({"status": "assign_executor", "summary": "next host turn"})["accepted"]


def test_invalid_done_can_be_corrected_and_does_not_publish(submit_module):
    m, target = submit_module
    assert not m._accept({"status": "done"})["accepted"]
    assert not target.exists()
    assert m._accept({"status": "assign_executor", "summary": "repair"})["accepted"]


def test_reviewer_reject_is_an_accepted_handoff(submit_module):
    m, target = submit_module
    m.KIND = "verdict"
    payload = {"verdict": "reject", "issues": [{"where": "claim", "problem": "missing", "expected": "evidence"}]}
    assert m._accept(payload)["accepted"]
    assert not m._accept({"verdict": "approve"})["accepted"]
    assert json.loads(target.read_text())["verdict"] == "reject"
