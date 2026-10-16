"""run e267986f: validate_providers_batch alone must satisfy exchange_unit_groups."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import olca_schema as o

from backend.core.agents.permission_narrow import resolve_permissions_narrowed
from backend.core.workflow.spec.loader import load_stage_spec
from harness.tools.shared.control_openlca import readonly
from harness.tools.shared.control_openlca import workflow as olca
from harness.tools.shared.lca_artifacts import checks
from harness.tools.shared.lca_artifacts.store import Context, invoke

REPO = Path(__file__).resolve().parents[5]
PROVIDER = "11111111-1111-1111-1111-111111111111"
FLOW = "22222222-2222-2222-2222-222222222222"


class _Client:
    def get(self, model, uid):
        out = o.Exchange(
            is_input=False,
            flow=o.Ref(id=FLOW, name="electricity"),
            unit=o.Ref(id="u", name="kWh"),
            flow_property=o.Ref(id="fp", name="Energy"),
        )
        return o.Process(id=uid, name="grid", exchanges=[out])


def _ctx(tmp_path, monkeypatch) -> Context:
    monkeypatch.setenv("LCA_IPC_LOCK_ROOT", str(tmp_path / "locks"))
    return Context(tmp_path, tmp_path / "workspace", "run-u", "03-dataset-mapping", 1)


def _inventory(_dir):
    ex = {"isInput": True, "amount": 1.0, "unit": {"name": "kWh"},
          "flow": {"@id": FLOW, "name": "electricity"}, "defaultProvider": {"@id": PROVIDER}}
    return [{"entity_type": "Process", "id": "fg", "path": "processes/fg.json",
             "data": {"exchanges": [ex]}}], []


def _validate(ctx):
    with patch.object(readonly, "create_ipc_client", return_value=_Client()), patch.object(
        readonly, "close_ipc_client"
    ):
        return invoke(
            "validate_providers_batch",
            lambda: readonly.validate_providers_batch(
                "localhost", 65530, [{"process_id": PROVIDER, "flow_id": FLOW}]
            ),
            ctx=ctx,
        )


def test_validate_only_evidence_satisfies_unit_groups(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch)
    lci = ctx.attempt_root() / "LCI"
    (lci / "processes").mkdir(parents=True)
    (lci / "processes" / "fg.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(olca, "load_lci_inventory", _inventory)
    _validate(ctx)
    raw = checks.current_provider_units(ctx)
    assert raw[(PROVIDER, FLOW)]["name"] == "kWh"
    errors, _ = checks.exchange_unit_errors(ctx, lci)
    assert errors == []
    # a markdown file inside LCI/ does not invalidate the evidence
    (lci / "human_readable_mapping.md").write_text("# notes", encoding="utf-8")
    assert checks.exchange_unit_errors(ctx, lci)[0] == []
    # changing LCI JSON does: the hint names a tool that records provider_unit
    (lci / "processes" / "fg.json").write_text(json.dumps({"x": 1}), encoding="utf-8")
    errors, _ = checks.exchange_unit_errors(ctx, lci)
    assert errors and "validate_providers_batch" in errors[0] and "provider_unit" in errors[0]


def test_lci_fingerprint_ignores_non_json(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch)
    lci = ctx.attempt_root() / "LCI"
    lci.mkdir(parents=True)
    (lci / "a.json").write_text("{}", encoding="utf-8")
    before = checks.lci_fingerprint(ctx)
    (lci / "human_readable_mapping.md").write_text("x", encoding="utf-8")
    assert checks.lci_fingerprint(ctx) == before
    (lci / "a.json").write_text("{\"a\":1}", encoding="utf-8")
    assert checks.lci_fingerprint(ctx) != before


def _denied(stage: str, role: str) -> list[str]:
    rel = f"harness/specs/{stage}/spec.yaml"
    spec = load_stage_spec(REPO / rel, project_root=REPO, relative=rel)
    res = resolve_permissions_narrowed(
        project_root=REPO, role=role, rule_refs=None,
        mcp_servers={"lca_artifacts": {}, "control_openlca": {}, "spec_mcp": {}},
        stage_spec=spec, attempt=1,
    )
    assert not res.error
    return res.deny_write_globs


def test_stage03_cannot_write_artifacts():
    target = str(REPO.resolve() / "workspace/artifacts/**")
    assert target in _denied("03-dataset-mapping", "executor")
    assert target in _denied("03-dataset-mapping", "reviser")
    assert target not in _denied("02-inventory-extraction", "executor")
