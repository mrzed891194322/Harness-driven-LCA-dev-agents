"""Generic spec.checks host interface (no built-in BOM gate)."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from backend.workflow import layout
from backend.workflow.checks import host_produce_errors, produce_errors, run_spec_checks
from backend.workflow.config import Spec


def _node(produces, node_id: str = "bom-extract-04"):
    return SimpleNamespace(produces=produces, requires=[], id=node_id, run_key=node_id, rev=0)


def _prod(spec: str, path: str = "bom/claims.json"):
    return SimpleNamespace(spec=spec, path=path)


def _best_check(**extra):
    base = {"id": "bom_claims_hard_warns", "load_knowledge": True, "checklist_from_run": True}
    base.update(extra)
    return base


def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    (ws / "artifacts").mkdir(parents=True)
    return ws


def _write_claims(ws: Path, node, payload: dict) -> Path:
    path = layout.produce_target(ws, node, "bom/claims.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_empty_checks_unchanged(tmp_path: Path):
    ws = _workspace(tmp_path)
    payload = {"claims": [{"claim_id": "c1", "value": 1, "unit": "kg"}]}
    node = _node([_prod("s")], node_id="plain-node")
    _write_claims(ws, node, payload)
    spec = Spec(id="x", prompt="p", schema_={
        "type": "object", "required": ["claims"],
        "properties": {"claims": {"type": "array"}},
    }, checks=[])
    specs = {"s": spec}
    assert produce_errors(ws, node, specs) == []
    assert run_spec_checks(ws, node, specs) == []
    assert host_produce_errors(ws, node, specs) == []


def test_unknown_check_id_errors(tmp_path: Path):
    ws = _workspace(tmp_path)
    node = _node([_prod("s")])
    _write_claims(ws, node, {"claims": []})
    spec = Spec(id="x", prompt="p", schema_=None, checks=[{"id": "no_such_check"}])
    errs = run_spec_checks(ws, node, {"s": spec})
    assert errs and "未知 check" in errs[0]


def _checklist_path(ws: Path, node_id: str = "bom-extract-04") -> Path:
    return layout.node_checklist_path(ws, node_id)


def test_bom_hard_missing_checklist_contract(tmp_path: Path):
    ws = _workspace(tmp_path)
    node = _node([_prod("s")])
    _write_claims(ws, node, {"claims": []})
    spec = Spec(id="best", prompt="p", schema_=None, checks=[_best_check()])
    errs = run_spec_checks(ws, node, {"s": spec})
    assert errs and any("题面契约缺失" in e for e in errs)


def test_bom_hard_unmatched_over_report(tmp_path: Path):
    ws = _workspace(tmp_path)
    node = _node([_prod("s")])
    cl = _checklist_path(ws)
    cl.parent.mkdir(parents=True, exist_ok=True)
    cl.write_text(json.dumps({"items": ["steel frame mass"]}), encoding="utf-8")
    payload = {
        "claims": [
            {"claim_id": "a", "value": 1, "unit": "kg", "evidence": "1 kg", "text": "unrelated glass mass"},
            {"claim_id": "b", "value": 2, "unit": "kg", "evidence": "2 kg", "text": "steel frame mass"},
        ],
    }
    _write_claims(ws, node, payload)
    spec = Spec(id="best", prompt="p", schema_=None, checks=[_best_check()])
    errs = run_spec_checks(ws, node, {"s": spec})
    assert errs and any("未匹配任何清单项" in e for e in errs)


def test_bom_no_hard_empty_claims_with_checklist(tmp_path: Path):
    ws = _workspace(tmp_path)
    node = _node([_prod("s")])
    cl = _checklist_path(ws)
    cl.parent.mkdir(parents=True, exist_ok=True)
    cl.write_text(json.dumps({"items": ["a"]}), encoding="utf-8")
    _write_claims(ws, node, {"claims": []})
    spec = Spec(id="best", prompt="p", schema_=None, checks=[_best_check()])
    errs = run_spec_checks(ws, node, {"s": spec})
    assert not errs


def test_bom_no_hard_unit_phrase(tmp_path: Path):
    ws = _workspace(tmp_path)
    node = _node([_prod("s")])
    cl = _checklist_path(ws)
    cl.parent.mkdir(parents=True, exist_ok=True)
    cl.write_text(json.dumps({"items": ["mass"]}), encoding="utf-8")
    payload = {
        "claims": [{"claim_id": "a", "value": 3, "unit": "g", "evidence": "mass 3 kg"}],
    }
    _write_claims(ws, node, payload)
    spec = Spec(id="best", prompt="p", schema_=None, checks=[_best_check()])
    errs = run_spec_checks(ws, node, {"s": spec})
    assert not any("单位短语" in e for e in errs)


def test_bom_no_hard_count_mismatch_with_checklist(tmp_path: Path):
    ws = _workspace(tmp_path)
    node = _node([_prod("s")])
    cl = _checklist_path(ws)
    cl.parent.mkdir(parents=True, exist_ok=True)
    cl.write_text(json.dumps({"items": ["a", "b"]}), encoding="utf-8")
    payload = {"claims": [{"claim_id": "a", "value": 1, "unit": "kg", "evidence": "1 kg", "text": "a"}]}
    _write_claims(ws, node, payload)
    spec = Spec(id="best", prompt="p", schema_=None, checks=[_best_check()])
    errs = host_produce_errors(ws, node, {"s": spec})
    assert not any("条数" in e for e in errs)


def test_bom_hard_warns_far_apart_not_host_error(tmp_path: Path):
    ws = _workspace(tmp_path)
    node = _node([_prod("s")])
    cl = _checklist_path(ws)
    cl.parent.mkdir(parents=True, exist_ok=True)
    cl.write_text(json.dumps({"items": ["steel mass"]}), encoding="utf-8")
    payload = {
        "claims": [{"claim_id": "a", "value": 3, "unit": "kg", "evidence": "A 3 m; B 8 kg", "text": "steel mass"}],
    }
    _write_claims(ws, node, payload)
    spec = Spec(
        id="best",
        prompt="p",
        schema_=None,
        checks=[_best_check()],
    )
    errs = run_spec_checks(ws, node, {"s": spec})
    assert not any("相距较远" in e for e in errs)
