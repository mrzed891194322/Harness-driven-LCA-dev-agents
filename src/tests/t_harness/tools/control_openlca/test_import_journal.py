"""Import journal is preflights/ + operations/ only; receipts live in the operation file (SIMPLIFY #4d)."""

from __future__ import annotations

import json

import pytest

from harness.tools.shared.control_openlca import operations as ops

CAT = "202606-harness-agent-LCA"
INV = [{"id": "p1", "entity_type": "Process", "sha256": "a"}, {"id": "p2", "entity_type": "Process", "sha256": "b"}]


@pytest.fixture
def env(tmp_path, monkeypatch):
    lci = tmp_path / "LCI"
    lci.mkdir()
    (lci / "a.json").write_text("{}", encoding="utf-8")
    state = {"fail": set()}

    def inspect(host, port, lci_dir, cat, db, client):
        return {"ok": True, "errors": [], "preflight_hash": "h"}, list(INV), {}

    def execute(ipc, inventory, targets, cat, *, on_progress, entity_plan, **_):
        failed = 0
        for entry in entity_plan:
            if entry["id"] in state["fail"]:
                entry["status"] = "failed"
                failed += 1
            else:
                entry["status"] = "done"
        return [], len(entity_plan) - failed, failed, 0, []

    monkeypatch.setattr(ops, "_inspect_import", inspect)
    monkeypatch.setattr(ops, "_execute_import", execute)
    monkeypatch.setattr(ops, "prior_uncertain_marker", lambda *a: False)
    monkeypatch.setattr(ops, "build_entity_plan",
                        lambda inv: [{"id": i["id"], "status": "pending", "content_hash": i.get("sha256", "")} for i in inv])
    return {"lci": lci, "jd": tmp_path / "journal", "state": state}


def _pre(env):
    return ops.preflight("127.0.0.1", 8080, env["lci"], CAT, "db", run_id="r1", operation_dir=env["jd"], client=object())


def _imp(env, req, pf, **kw):
    return ops.import_request("127.0.0.1", 8080, env["lci"], CAT, "db", run_id="r1", request_id=req,
                              preflight_id=pf, operation_dir=env["jd"], client=object(), **kw)


def _dirs(env):
    return sorted(p.name for p in env["jd"].iterdir())


def test_success_writes_only_preflights_and_operations(env):
    pf = _pre(env)["preflight_id"]
    rep = _imp(env, "q1", pf)
    assert rep["status"] == "success"
    assert _dirs(env) == ["operations", "preflights"]
    saved = json.loads((env["jd"] / "operations" / f"{rep['operation_id']}.json").read_text())
    assert saved["request_ids"] == ["q1"] and saved["preflight_ids"] == [pf]
    # same request is reused; same preflight cannot authorize a second request
    assert _imp(env, "q1", pf)["execution_mode"] == "reused"
    assert _imp(env, "q2", pf)["errors"] == ["preflight_already_consumed"]
    assert ops.get_operation(env["jd"], run_id="r1")["operation_id"] == rep["operation_id"]
    assert ops.get_operation(env["jd"], run_id="r1", request_id="q1")["operation_id"] == rep["operation_id"]
    assert ops.get_operation(env["jd"], run_id="r1", request_id="nope")["status"] == "not_found"


def test_partial_failure_blocks_fresh_import_and_resumes(env):
    env["state"]["fail"] = {"p2"}
    first = _imp(env, "q1", _pre(env)["preflight_id"])
    assert first["status"] == "partial_failure"
    blocked = _imp(env, "q2", _pre(env)["preflight_id"])
    assert blocked["errors"] == ["previous import requires reconciliation"]
    env["state"]["fail"] = set()
    resumed = _imp(env, "q3", _pre(env)["preflight_id"], resume_operation_id=first["operation_id"])
    assert resumed["status"] == "success" and resumed["execution_mode"] == "resumed"
    saved = json.loads((env["jd"] / "operations" / f"{first['operation_id']}.json").read_text())
    assert saved["request_ids"] == ["q1", "q3"]
    assert ops.get_operation(env["jd"], run_id="r1", request_id="q3")["operation_id"] == first["operation_id"]
    assert _dirs(env) == ["operations", "preflights"]


def test_cleanup_clears_current_in_operation_file(env):
    env["state"]["fail"] = {"p2"}
    first = _imp(env, "q1", _pre(env)["preflight_id"])
    ops.reconcile_cleanup(env["jd"], "127.0.0.1", 8080, "other-category")
    assert ops.current_operation(env["jd"]) is not None  # wrong category: untouched
    ops.reconcile_cleanup(env["jd"], "127.0.0.1", 8080, CAT)
    assert ops.current_operation(env["jd"]) is None
    saved = json.loads((env["jd"] / "operations" / f"{first['operation_id']}.json").read_text())
    assert saved["cleared"]["reason"] == "explicit cleanup completed"
    env["state"]["fail"] = set()
    assert _imp(env, "q2", _pre(env)["preflight_id"])["status"] == "success"
    assert _dirs(env) == ["operations", "preflights"]


def test_unreadable_operation_fails_closed(env):
    _imp(env, "q1", _pre(env)["preflight_id"])
    (env["jd"] / "operations" / "zz.json").write_text("{broken", encoding="utf-8")
    rep = _imp(env, "q2", _pre(env)["preflight_id"])
    assert rep["status"] == "indeterminate"
