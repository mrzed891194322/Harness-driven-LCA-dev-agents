"""Thin MCP check_claims: warn-only; never mutates claims; no blacklist / hard gate."""
from __future__ import annotations

import json
from pathlib import Path

import harness.tools.shared.bom_claims_check as pkg
from harness.tools.shared.bom_claims_check.validate import (
    check_claims_file,
    check_claims_payload,
)


def _one(claim, **kw):
    return check_claims_payload({"claims": [claim]}, **kw)


def test_no_blacklist_or_hard_errors():
    assert not hasattr(pkg, "BLACKLIST_UNITS") and not hasattr(pkg, "hard_errors_for_host")
    out = _one({"claim_id": "c1", "value": 2, "unit": "h", "evidence": "f.md L3: takes 2 h"})
    assert "hard_errors" not in out and "ok" not in out
    assert out["status"] == "checked" and out["warnings"] == [] and out["auto_deleted"] is False
    assert out["claims"][0]["value_unit"] == "near"


def test_payload_not_mutated():
    data = {"claims": [{"claim_id": "c1", "value": 9, "unit": "kg", "evidence": "x 3 kg"}]}
    before = json.dumps(data)
    out = check_claims_payload(data)
    assert json.dumps(data) == before and out["warnings"]
    assert not any("删除" in w or "必须" in w for w in out["warnings"])


def test_unit_case_and_word_boundary():
    assert _one({"claim_id": "a", "value": 3, "unit": "g", "evidence": "3 kg"})["warnings"]
    assert _one({"claim_id": "a", "value": 3, "unit": "mJ", "evidence": "3 MJ"})["warnings"]
    assert not _one({"claim_id": "a", "value": 3, "unit": "MJ", "evidence": "3 MJ"})["warnings"]


def test_value_must_be_near_its_unit():
    out = _one({"claim_id": "a", "value": 3, "unit": "kg", "evidence": "A 3 m; B 8 kg"})
    assert out["claims"][0]["value_unit"] == "far_apart"


def test_minus_vs_range_dash():
    assert not _one({"claim_id": "a", "value": 5, "unit": "%", "evidence": "loss 2–5 %"})["warnings"]
    assert not _one({"claim_id": "a", "value": -5, "unit": "%", "evidence": "net −5 %"})["warnings"]
    assert _one({"claim_id": "a", "value": 5, "unit": "%", "evidence": "net -5 %"})["warnings"]


def test_leading_dot_decimal_comma_and_exact():
    assert not _one({"claim_id": "a", "value": 0.5, "unit": "kg", "evidence": ".5 kg"})["warnings"]
    assert not _one({"claim_id": "a", "value": 1.5, "unit": "kg", "evidence": "1,5 kg"})["warnings"]
    assert _one({"claim_id": "a", "value": 0, "unit": "kg", "evidence": "1e-12 kg"})["warnings"]


def test_structural_warnings_separate():
    out = check_claims_payload({"claims": [
        {"claim_id": "a", "value": True, "unit": "kg", "evidence": "1 kg"},
        {"claim_id": "b", "value": None, "unit": "kg", "evidence": "x"},
        {"claim_id": "c", "value": 1, "unit": "kg", "evidence": 5},
    ]})
    s = " ".join(out["structural_warnings"])
    assert "布尔" in s and "成对" in s and "evidence 不是字符串" in s


def test_missing_evidence_vs_inferred_mark():
    out = _one({"claim_id": "a", "value": 1, "unit": "kg"})
    assert any("[推断]" in w for w in out["warnings"])
    out = _one({"claim_id": "a", "value": 1, "unit": "kg", "evidence": "[推断] 由 f.md 表2 两行相加"})
    assert out["warnings"] == [] and out["claims"][0]["value_unit"] == "inferred"
    assert _one({"claim_id": "a", "value": 1, "unit": "kg", "evidence": "[推断]"})["warnings"]


def test_evidence_source_lookup():
    c = {"claim_id": "a", "value": 1, "unit": "kg", "evidence": "weighs 1 kg"}
    assert _one(c, sources=["The box weighs  1 kg in total."])["claims"][0]["evidence_source"] == "found"
    assert _one(c, sources=["nothing"])["claims"][0]["evidence_source"] == "not_found"
    assert _one(c)["claims"][0]["evidence_source"] == "unavailable"


def test_file_roundtrip_no_write(tmp_path: Path):
    path = tmp_path / "claims.json"
    path.write_text(json.dumps({"claims": [{"claim_id": "c1", "value": 1, "unit": "hr"}]}), encoding="utf-8")
    raw, mtime = path.read_bytes(), path.stat().st_mtime_ns
    result = check_claims_file(path)
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == mtime
    assert result["status"] == "checked"
    assert check_claims_file(tmp_path / "nope.json")["status"] == "unavailable"


def test_source_unit_phrase_verbatim():
    """unit must be the source phrase (word-boundary); short symbols that drop qualifiers warn."""
    ok = {"claim_id": "a", "value": 12, "unit": "kg N/ha", "evidence": "f.md T1: rate 12 kg N/ha"}
    assert not _one(ok)["warnings"] and _one(ok)["claims"][0]["value_unit"] == "near"
    short = {"claim_id": "a", "value": 12, "unit": "kg/ha", "evidence": "f.md T1: rate 12 kg N/ha"}
    out = _one(short)
    assert out["warnings"] and out["claims"][0]["value_unit"] == "unit_not_verbatim"
    phrase = {
        "claim_id": "a",
        "value": 0.4,
        "unit": "% of dissolved tin",
        "evidence": "share is 0.4 % of dissolved tin",
    }
    assert not _one(phrase)["warnings"]
