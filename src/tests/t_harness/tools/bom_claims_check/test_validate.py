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


def _warn_body(out):
    """Warnings excluding the missing-expected_count reminder (when N not passed)."""
    return [w for w in out["warnings"] if "未提供 checklist" not in w]


def test_no_blacklist_or_hard_errors():
    assert not hasattr(pkg, "BLACKLIST_UNITS") and not hasattr(pkg, "hard_errors_for_host")
    out = _one({"claim_id": "c1", "value": 2, "unit": "h", "evidence": "f.md L3: takes 2 h"}, expected_count=1)
    assert "hard_errors" not in out and "ok" not in out
    assert out["status"] == "checked" and out["warnings"] == [] and out["auto_deleted"] is False
    assert out["claims"][0]["value_unit"] == "near"


def test_payload_not_mutated():
    data = {"claims": [{"claim_id": "c1", "value": 9, "unit": "kg", "evidence": "x 3 kg"}]}
    before = json.dumps(data)
    out = check_claims_payload(data, expected_count=1)
    assert json.dumps(data) == before and out["warnings"]
    assert not any("删除" in w or "必须" in w for w in out["warnings"])


def test_unit_case_and_word_boundary():
    assert _warn_body(_one({"claim_id": "a", "value": 3, "unit": "g", "evidence": "3 kg"}))
    assert _warn_body(_one({"claim_id": "a", "value": 3, "unit": "mJ", "evidence": "3 MJ"}))
    assert not _warn_body(_one({"claim_id": "a", "value": 3, "unit": "MJ", "evidence": "3 MJ"}, expected_count=1))


def test_value_must_be_near_its_unit():
    out = _one({"claim_id": "a", "value": 3, "unit": "kg", "evidence": "A 3 m; B 8 kg"}, expected_count=1)
    assert out["claims"][0]["value_unit"] == "far_apart"


def test_minus_vs_range_dash():
    assert not _one({"claim_id": "a", "value": 5, "unit": "%", "evidence": "loss 2–5 %"}, expected_count=1)["warnings"]
    assert not _one({"claim_id": "a", "value": -5, "unit": "%", "evidence": "net −5 %"}, expected_count=1)["warnings"]
    assert _warn_body(_one({"claim_id": "a", "value": 5, "unit": "%", "evidence": "net -5 %"}, expected_count=1))


def test_leading_dot_decimal_comma_and_exact():
    assert not _one({"claim_id": "a", "value": 0.5, "unit": "kg", "evidence": ".5 kg"}, expected_count=1)["warnings"]
    assert not _one({"claim_id": "a", "value": 1.5, "unit": "kg", "evidence": "1,5 kg"}, expected_count=1)["warnings"]
    assert _warn_body(_one({"claim_id": "a", "value": 0, "unit": "kg", "evidence": "1e-12 kg"}, expected_count=1))


def test_structural_warnings_separate():
    out = check_claims_payload({"claims": [
        {"claim_id": "a", "value": True, "unit": "kg", "evidence": "1 kg"},
        {"claim_id": "b", "value": None, "unit": "kg", "evidence": "x"},
        {"claim_id": "c", "value": 1, "unit": "kg", "evidence": 5},
    ]}, expected_count=3)
    s = " ".join(out["structural_warnings"])
    assert "布尔" in s and "成对" in s and "evidence 不是字符串" in s


def test_missing_evidence_vs_inferred_mark():
    out = _one({"claim_id": "a", "value": 1, "unit": "kg"}, expected_count=1)
    assert any("[推断]" in w for w in out["warnings"])
    out = _one({"claim_id": "a", "value": 1, "unit": "kg", "evidence": "[推断] 由 f.md 表2 两行相加"}, expected_count=1)
    assert out["warnings"] == [] and out["claims"][0]["value_unit"] == "inferred"
    assert _warn_body(_one({"claim_id": "a", "value": 1, "unit": "kg", "evidence": "[推断]"}, expected_count=1))


def test_evidence_source_lookup():
    c = {"claim_id": "a", "value": 1, "unit": "kg", "evidence": "weighs 1 kg"}
    assert _one(c, sources=["The box weighs  1 kg in total."], expected_count=1)["claims"][0]["evidence_source"] == "found"
    assert _one(c, sources=["nothing"], expected_count=1)["claims"][0]["evidence_source"] == "not_found"
    assert _one(c, expected_count=1)["claims"][0]["evidence_source"] == "unavailable"


def test_file_roundtrip_no_write(tmp_path: Path):
    path = tmp_path / "claims.json"
    path.write_text(json.dumps({"claims": [{"claim_id": "c1", "value": 1, "unit": "hr"}]}), encoding="utf-8")
    raw, mtime = path.read_bytes(), path.stat().st_mtime_ns
    result = check_claims_file(path, expected_count=1)
    assert path.read_bytes() == raw and path.stat().st_mtime_ns == mtime
    assert result["status"] == "checked"
    assert check_claims_file(tmp_path / "nope.json")["status"] == "unavailable"


def test_source_unit_phrase_verbatim():
    """unit must be the source phrase (word-boundary); short symbols that drop qualifiers warn."""
    ok = {"claim_id": "a", "value": 12, "unit": "kg N/ha", "evidence": "f.md T1: rate 12 kg N/ha"}
    assert not _one(ok, expected_count=1)["warnings"] and _one(ok, expected_count=1)["claims"][0]["value_unit"] == "near"
    short = {"claim_id": "a", "value": 12, "unit": "kg/ha", "evidence": "f.md T1: rate 12 kg N/ha"}
    out = _one(short, expected_count=1)
    assert out["warnings"] and out["claims"][0]["value_unit"] == "unit_not_verbatim"
    phrase = {
        "claim_id": "a",
        "value": 0.4,
        "unit": "% of dissolved tin",
        "evidence": "share is 0.4 % of dissolved tin",
    }
    assert not _one(phrase, expected_count=1)["warnings"]


def test_expected_count_match_no_count_warning():
    claims = [
        {"claim_id": "a", "value": 1, "unit": "kg", "evidence": "1 kg"},
        {"claim_id": "b", "value": 2, "unit": "kg", "evidence": "2 kg"},
    ]
    out = check_claims_payload({"claims": claims}, expected_count=2)
    assert out["status"] == "checked" and out["auto_deleted"] is False
    assert out["claim_count"] == 2
    assert not any("题面清单 N=" in w for w in out["warnings"])
    assert not any("未提供 checklist" in w for w in out["warnings"])


def test_expected_count_mismatch_warn_only():
    claims = [{"claim_id": "a", "value": 1, "unit": "kg", "evidence": "1 kg"}]
    out = check_claims_payload({"claims": claims}, expected_count=3)
    assert out["status"] == "checked" and out["auto_deleted"] is False
    assert "hard_errors" not in out
    assert any("claims 条数 1 ≠ 题面清单 N=3" in w and "疑似漏报" in w for w in out["warnings"])
    for bad in ("勿按告警批量删条", "告警不要求清零"):
        assert not any(bad in w for w in out["warnings"])
    # still does not mutate
    assert len(claims) == 1


def test_expected_count_missing_reminds_and_skips():
    out = check_claims_payload(
        {"claims": [{"claim_id": "a", "value": 1, "unit": "kg", "evidence": "1 kg"}]}
    )
    assert any("未提供 checklist" in w for w in out["warnings"])
    assert not any("题面清单 N=" in w for w in out["warnings"])


def test_expected_count_invalid_skips():
    out = check_claims_payload(
        {"claims": [{"claim_id": "a", "value": 1, "unit": "kg", "evidence": "1 kg"}]},
        expected_count=-1,
    )
    assert any("非法" in w for w in out["warnings"])
    assert not any("claims 条数" in w for w in out["warnings"])


def test_expected_count_never_hard_gate_or_gold():
    """Contract: count check is warn-only; no hard_errors / ok / auto_deleted."""
    out = check_claims_payload({"claims": []}, expected_count=5)
    assert out["auto_deleted"] is False
    assert "hard_errors" not in out and "ok" not in out
    # empty + not abstained already warns; plus count mismatch
    assert any("题面清单 N=5" in w for w in out["warnings"])


def test_checklist_sets_count_and_flags_missing():
    data = {"claims": [{"claim_id": "a", "text": "steel frame mass", "value": 3, "unit": "kg", "evidence": "3 kg"}]}
    out = check_claims_payload(data, checklist=["steel frame mass", "glass mass"])
    joined = " ".join(out["warnings"])
    assert "N=2" in joined and "glass mass" in joined
    assert "疑似漏报" in joined
    assert out["auto_deleted"] is False and len(data["claims"]) == 1


def test_checklist_match_no_count_warning():
    data = {"claims": [{"claim_id": "a", "value": 3, "unit": "kg", "evidence": "3 kg"}]}
    out = check_claims_payload(data, checklist=["x"])
    assert not out["warnings"]


def test_checklist_flags_extra():
    data = {"claims": [
        {"claim_id": "a", "text": "frame", "value": 3, "unit": "kg", "evidence": "3 kg"},
        {"claim_id": "b", "text": "solvent", "value": 4, "unit": "kg", "evidence": "4 kg"},
    ]}
    out = check_claims_payload(data, checklist=["frame"])
    joined = " ".join(out["warnings"])
    assert "若条数 > N" in joined and "须删去多余条" in joined
    assert any("'b'" in w and "多报" in w for w in out["warnings"])


def test_coverage_hints_token_match_item_id_field():
    """Legal fields + token overlap: matching claim kept out of 多报 list."""
    data = {"claims": [
        {"claim_id": "keep", "item_id": "steel", "field": "mass", "value": 3, "unit": "kg", "evidence": "3 kg"},
        {"claim_id": "drop", "text": "solvent volume", "value": 4, "unit": "L", "evidence": "4 L"},
    ]}
    out = check_claims_payload(data, checklist=["steel frame mass"])
    extra_warns = [w for w in out["warnings"] if "可能多报" in w]
    assert extra_warns and "'drop'" in extra_warns[0] and "'keep'" not in extra_warns[0]


def test_message_has_no_exemption_openings():
    out = check_claims_payload(
        {"claims": [{"claim_id": "a", "value": 1, "unit": "kg", "evidence": "1 kg"}]},
        expected_count=1,
    )
    msg = out["message"]
    assert "仅提醒" in msg and "未改写" in msg
    for bad in ("告警不要求清零", "不要按告警批量删条", "勿按告警批量删条"):
        assert bad not in msg


def test_bad_checklist_ignored_with_warning():
    out = check_claims_payload({"claims": []}, checklist=["", 3])
    assert any("checklist" in w for w in out["warnings"])


def test_correctness_value_not_in_evidence_and_not_in_source():
    data = {"claims": [{"claim_id": "a", "value": 7, "unit": "kg", "evidence": "f.md: 3 kg"}]}
    out = check_claims_payload(data, sources=["other text"], checklist=["a"])
    joined = " ".join(out["warnings"])
    assert "未在 evidence" in joined and "未逐字找到" in joined


def test_correctness_inferred_not_warned():
    data = {"claims": [{"claim_id": "a", "value": 7, "unit": "kg", "evidence": "[推断] 按 f.md 表 2 推算"}]}
    assert not check_claims_payload(data, sources=["x"], checklist=["a"])["warnings"]
