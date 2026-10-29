"""Generic spec.checks host interface (post-deliver narrow gate)."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from backend.workflow.checks import host_produce_errors, produce_errors, run_spec_checks
from backend.workflow.config import Spec


def _node(produces):
    return SimpleNamespace(produces=produces, requires=[])


def _prod(spec: str, path: str = "bom/claims.json"):
    return SimpleNamespace(spec=spec, path=path)


def test_empty_checks_unchanged(tmp_path: Path):
    art = tmp_path
    target = art / "bom"
    target.mkdir()
    (target / "claims.json").write_text(
        json.dumps({"claims": [{"claim_id": "c1", "value": 1, "unit": "kg"}]}),
        encoding="utf-8",
    )
    spec = Spec(id="x", prompt="p", schema_={
        "type": "object", "required": ["claims"],
        "properties": {"claims": {"type": "array"}},
    }, checks=[])
    node = _node([_prod("s")])
    specs = {"s": spec}
    assert produce_errors(art, node, specs) == []
    assert run_spec_checks(art, node, specs) == []
    assert host_produce_errors(art, node, specs) == []


def test_blacklist_check_gates_host(tmp_path: Path):
    art = tmp_path
    (art / "bom").mkdir()
    (art / "bom" / "claims.json").write_text(
        json.dumps({"claims": [{"claim_id": "bad", "value": 3, "unit": "h"}]}),
        encoding="utf-8",
    )
    schema = {
        "type": "object",
        "required": ["claims"],
        "properties": {
            "claims": {"type": "array"},
            "abstained": {"type": "boolean"},
        },
    }
    spec = Spec(
        id="bom-claims-02",
        prompt="p",
        schema_=schema,
        checks=[{"id": "bom_claims_blacklist_units"}],
    )
    node = _node([_prod("s")])
    specs = {"s": spec}
    # schema alone passes
    assert produce_errors(art, node, specs) == []
    errs = host_produce_errors(art, node, specs)
    assert errs and any("黑名单" in e or "h" in e for e in errs)


def test_unknown_check_id_errors(tmp_path: Path):
    art = tmp_path
    (art / "bom").mkdir()
    (art / "bom" / "claims.json").write_text(json.dumps({"claims": []}), encoding="utf-8")
    spec = Spec(id="x", prompt="p", schema_=None, checks=[{"id": "no_such_check"}])
    errs = run_spec_checks(art, _node([_prod("s")]), {"s": spec})
    assert errs and "未知 check" in errs[0]
