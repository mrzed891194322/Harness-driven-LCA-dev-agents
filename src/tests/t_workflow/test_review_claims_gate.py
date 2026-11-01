"""Host review_claims_gate: block reviewer approve on bom hard-ish warning codes."""
from __future__ import annotations

import json
import shutil

from backend.workflow import layout
from backend.workflow.checks import review_claims_gate_errors
from backend.workflow.config import Spec, load_workflow
from backend.workflow.runner import Runner
from tests.t_workflow.conftest import make_node, node_ref, spec_ref, write_yaml
from tests.t_workflow.fake_driver import FakeDriver
from tests.t_workflow.test_spec_checks import _best_check, _checklist_path, _node, _prod, _workspace, _write_claims

REPO = __import__("pathlib").Path(__file__).resolve().parents[3]


def _bom_spec_yaml(root):
    src = REPO / ".benchmark/bom/harness/specs/bom-claims-best.yaml"
    shutil.copy(src, root / "harness/specs/bom-claims-best.yaml")


def _bom_trio_wf(root):
    _bom_spec_yaml(root)
    agents = {
        "orchestrator": "orchestrator",
        "executor": {"prompt": "写", "access": {"read": {"knowledge": True, "artifacts": True}}},
        "reviewer": "reviewer",
    }
    make_node(
        root,
        "bom",
        produces=[{"spec": spec_ref("bom-claims-best"), "path": "bom/claims.json"}],
        agents=agents,
    )
    write_yaml(root / "harness/workflows/orchestrations/bom-trio.yaml", {"nodes": [node_ref("bom")]})
    return load_workflow(root, "bom-trio")


def _events(root):
    path = root / "workspace/runs/_run/events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_review_claims_gate_errors_unmatched(tmp_path):
    ws = _workspace(tmp_path)
    node = _node([_prod("bom-claims-best")])
    cl = _checklist_path(ws)
    cl.parent.mkdir(parents=True, exist_ok=True)
    cl.write_text(json.dumps({"items": ["steel frame mass"]}), encoding="utf-8")
    _write_claims(
        ws,
        node,
        {
            "claims": [
                {"claim_id": "a", "text": "glass mass", "value": 1, "unit": "kg", "evidence": "1 kg"},
            ],
        },
    )
    spec = Spec(id="best", prompt="p", schema_=None, checks=[_best_check()])
    errs = review_claims_gate_errors(ws, node, {"bom-claims-best": spec})
    assert errs and any("CLAIMS_UNMATCHED_CHECKLIST" in e for e in errs)


def test_review_claims_gate_errors_empty_claims(tmp_path):
    ws = _workspace(tmp_path)
    node = _node([_prod("bom-claims-best")])
    cl = _checklist_path(ws)
    cl.parent.mkdir(parents=True, exist_ok=True)
    cl.write_text(json.dumps({"items": ["a"]}), encoding="utf-8")
    _write_claims(ws, node, {"claims": []})
    spec = Spec(id="best", prompt="p", schema_=None, checks=[_best_check()])
    errs = review_claims_gate_errors(ws, node, {"bom-claims-best": spec})
    assert any("CLAIMS_EMPTY_NO_ABSTAIN" in e for e in errs)


def test_review_claims_gate_same_slot_extra_only_ok(tmp_path):
    ws = _workspace(tmp_path)
    node = _node([_prod("bom-claims-best")])
    cl = _checklist_path(ws)
    cl.parent.mkdir(parents=True, exist_ok=True)
    cl.write_text(
        json.dumps({"items": ["Lower heating value (LHV) of fuel in MJ/kg"]}),
        encoding="utf-8",
    )
    _write_claims(
        ws,
        node,
        {
            "claims": [
                {
                    "claim_id": "c1",
                    "text": "LHV 2.4 MJ/kg",
                    "value": 2.4,
                    "unit": "MJ/kg",
                    "evidence": "LHV 2.4 MJ/kg",
                },
                {
                    "claim_id": "c2",
                    "text": "LHV 5.0 MJ/kg",
                    "value": 5.0,
                    "unit": "MJ/kg",
                    "evidence": "also 5.0 MJ/kg",
                },
            ],
        },
    )
    spec = Spec(id="best", prompt="p", schema_=None, checks=[_best_check()])
    assert review_claims_gate_errors(ws, node, {"bom-claims-best": spec}) == []


def test_review_claims_gate_count_mismatch_only_ok(tmp_path):
    ws = _workspace(tmp_path)
    node = _node([_prod("bom-claims-best")])
    cl = _checklist_path(ws)
    cl.parent.mkdir(parents=True, exist_ok=True)
    cl.write_text(
        json.dumps({"items": ["keyboard × unit weight in lb or g/kg"]}),
        encoding="utf-8",
    )
    _write_claims(
        ws,
        node,
        {
            "claims": [
                {
                    "claim_id": "c1",
                    "text": "keyboard unit weight",
                    "value": 1.32,
                    "unit": "lb",
                    "evidence": "1.32 lb",
                },
                {
                    "claim_id": "c2",
                    "text": "keyboard unit weight",
                    "value": 0.6,
                    "unit": "kg",
                    "evidence": "0.6 kg",
                },
            ],
        },
    )
    spec = Spec(id="best", prompt="p", schema_=None, checks=[_best_check()])
    assert review_claims_gate_errors(ws, node, {"bom-claims-best": spec}) == []


def test_reviewer_approve_rejected_on_unmatched(wf_root):
    cl = layout.node_checklist_path(wf_root, "bom")
    cl.parent.mkdir(parents=True, exist_ok=True)
    cl.write_text(json.dumps({"items": ["steel frame mass"]}), encoding="utf-8")
    claims_body = json.dumps(
        {
            "claims": [
                {"claim_id": "a", "text": "glass mass", "value": 1, "unit": "kg", "evidence": "1 kg"},
            ],
        }
    )
    d = FakeDriver({("bom", "executor"): [claims_body], ("bom", "reviewer"): ["approve"]})
    wf, nodes = _bom_trio_wf(wf_root)
    Runner(wf_root, wf, nodes, d, retry_interval=0).run(plans={"main_plan.md": "# 计划\n"})
    rej = [
        e
        for e in _events(wf_root)
        if e.get("kind") == "submit_rejected" and e.get("gate") == "review_claims_gate"
    ]
    assert rej
