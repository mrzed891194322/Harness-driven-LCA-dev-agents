"""Thin MCP / host gate: warn-only validate; never mutates claims."""
from __future__ import annotations

import json
from pathlib import Path

from harness.tools.shared.bom_claims_check.validate import (
    check_claims_file,
    check_claims_payload,
    hard_errors_for_host,
)


def test_blacklist_unit_is_hard_error_not_mutation():
    data = {
        "claims": [
            {"claim_id": "c1", "value": 2, "unit": "h", "evidence": "x"},
            {"claim_id": "c2", "value": 70, "unit": "°C", "text": "temp"},
            {"claim_id": "c3", "value": 1.2, "unit": "kg", "evidence": "ok"},
        ]
    }
    before = json.dumps(data, ensure_ascii=False)
    out = check_claims_payload(data)
    assert json.dumps(data, ensure_ascii=False) == before  # no mutation
    assert out["ok"] is False
    assert len(out["hard_errors"]) >= 2
    assert any("c1" in e and "h" in e for e in out["hard_errors"])
    assert any("c2" in e for e in out["hard_errors"])
    assert out["claim_count"] == 3


def test_good_claims_ok_with_soft_warnings_optional():
    data = {
        "claims": [
            {"claim_id": "c1", "value": 10, "unit": "%", "evidence": "L12 tin loss"},
        ]
    }
    out = check_claims_payload(data)
    assert out["ok"] is True
    assert out["hard_errors"] == []


def test_empty_non_abstained_is_warning_only():
    out = check_claims_payload({"claims": []})
    assert out["ok"] is True
    assert out["hard_errors"] == []
    assert any("空" in w or "abstain" in w.lower() for w in out["warnings"])


def test_file_roundtrip_no_write(tmp_path: Path):
    path = tmp_path / "claims.json"
    payload = {"claims": [{"claim_id": "c1", "value": 1, "unit": "hr"}]}
    path.write_text(json.dumps(payload), encoding="utf-8")
    mtime = path.stat().st_mtime_ns
    raw = path.read_bytes()
    result = check_claims_file(path)
    assert path.read_bytes() == raw
    assert path.stat().st_mtime_ns == mtime
    assert result["ok"] is False
    assert hard_errors_for_host(path)
