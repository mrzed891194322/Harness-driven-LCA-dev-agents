"""Claim F1 strict alignment and micro-F1 denominator tests."""

from __future__ import annotations

import importlib.util
import json
import statistics
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCORE_BATCH = REPO / ".benchmark" / "scripts" / "score_batch.py"
CLAIM_F1 = REPO / ".benchmark" / "bom" / "scorers" / "claim_f1.py"
CLAIM_F1_STRICT = REPO / ".benchmark" / "bom" / "scorers" / "claim_f1_strict.py"
MAIN_IMPORTED = Path(
    "/home/yuandu/Programming/202606-harness-agent-LCA/.benchmark/imported/bom/extract"
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _official_counts(gold: dict, pred: dict):
    strict = _load(
        REPO / ".benchmark/bom/scorers/pcfbench_official/extraction.py",
        "official_extraction",
    )
    unit_mod = _load(
        REPO / ".benchmark/bom/scorers/pcfbench_official/unit_normalization.py",
        "official_unit",
    )
    # silence unused
    assert unit_mod.normalize_unit("%") == "percent"

    def tuples(doc):
        out = []
        for c in doc.get("claims") or []:
            v, u = c.get("value"), c.get("unit")
            if v is not None and u:
                out.append((float(v), str(u)))
        return out

    gt, pr = tuples(gold), tuples(pred)
    matches, _, _ = strict._match_extraction_claims(pr, gt)
    matched = len(matches)
    return matched, len(pr), len(gt)


def test_strict_score_matches_official_matcher():
    cf1s = _load(CLAIM_F1_STRICT, "claim_f1_strict")
    gold = {
        "claims": [
            {"value": 0.5, "unit": "mass%"},
            {"value": 1000, "unit": "g/kg"},
        ]
    }
    pred = {
        "claims": [
            {"value": 50, "unit": "%"},
            {"value": 1, "unit": "kg/kg"},
            {"value": 99, "unit": "kg/kg"},
        ]
    }
    got = cf1s.score_claims(gold, pred)
    matched, n_pred, n_gold = _official_counts(gold, pred)
    assert got["matched"] == matched
    assert got["n_pred"] == n_pred
    assert got["n_gold"] == n_gold
    assert got["f1"] == pytest.approx(
        2
        * (matched / n_pred)
        * (matched / n_gold)
        / ((matched / n_pred) + (matched / n_gold))
    )


def test_zero_pred_includes_gold_in_micro_denominator():
    sb = _load(SCORE_BATCH, "score_batch")
    cf1 = _load(CLAIM_F1, "claim_f1")
    cf1s = _load(CLAIM_F1_STRICT, "claim_f1_strict")
    gold = {"claims": [{"value": 1.0, "unit": "kg"}, {"text": "note only"}]}
    z = sb._zero_claim_row(
        claim_f1=cf1,
        claim_f1_strict=cf1s,
        gold=gold,
        reason="no_submit",
        subcategory="extract",
    )
    assert z["n_gold"] == 1
    assert z["ext_n_gold"] == 2
    assert z["strict_n_gold"] == 1
    assert z["matched"] == 0
    assert z["f1"] == 0.0
    summary = sb.aggregate(
        [
            {
                **z,
                "category": "bom",
                "subcategory": "extract",
                "case_id": "c1",
                "run_id": "r1",
                "model": "m",
                "workflow": "bom-extract-03",
            }
        ]
    )
    suite = summary["by_suite"]["bom/extract"]
    assert suite["micro_n_gold"] == 1
    assert suite["strict_micro_n_gold"] == 1
    assert suite["ext_micro_n_gold"] == 2
    assert suite["macro_f1"] == 0.0


def test_extended_extra_mass_not_in_strict():
    cf1 = _load(CLAIM_F1, "claim_f1")
    cf1s = _load(CLAIM_F1_STRICT, "claim_f1_strict")
    gold = {"claims": [{"value": 1.0, "unit": "kg"}]}
    pred = {"claims": [{"value": 1000.0, "unit": "g"}]}
    assert cf1.score_claims(gold, pred)["matched"] == 1
    assert cf1s.score_claims(gold, pred)["matched"] == 0


def test_empty_both_extended_vs_strict():
    cf1 = _load(CLAIM_F1, "claim_f1")
    cf1s = _load(CLAIM_F1_STRICT, "claim_f1_strict")
    empty = {"claims": []}
    assert cf1.score_claims(empty, empty)["f1"] == 1.0
    assert cf1s.score_claims(empty, empty)["f1"] == 0.0


@pytest.mark.skipif(not MAIN_IMPORTED.is_dir(), reason="main repo imported tree")
def test_strict_on_real_gold_perturbed():
    cf1s = _load(CLAIM_F1_STRICT, "claim_f1_strict")
    case_dirs = sorted(d for d in MAIN_IMPORTED.iterdir() if d.is_dir())[:3]
    for case_dir in case_dirs:
        truth = json.loads((case_dir / "truth" / "claims.json").read_text())
        claims = truth.get("claims") or []
        if not claims:
            continue
        perturbed = {
            "claims": [
                dict(c, unit=str(c.get("unit") or "") + ", notes")
                if c.get("value") is not None and c.get("unit")
                else c
                for c in claims
            ]
        }
        got = cf1s.score_claims(truth, perturbed)
        matched, n_pred, n_gold = _official_counts(truth, perturbed)
        assert got["matched"] == matched
        assert got["n_pred"] == n_pred
        assert got["n_gold"] == n_gold


def test_run_claim_f1_micro_with_no_output_rows():
    sb = _load(SCORE_BATCH, "score_batch")
    cf1 = _load(CLAIM_F1, "claim_f1")
    cf1s = _load(CLAIM_F1_STRICT, "claim_f1_strict")
    gold = {"claims": [{"value": 2.0, "unit": "kg"}]}
    ext = cf1.score_claims(gold, gold)
    strict = cf1s.score_claims(gold, gold)
    hit: dict = {
        "category": "bom",
        "subcategory": "extract",
        "case_id": "c-hit",
        "run_id": "r1",
    }
    sb._apply_claim_f1_row(hit, ext=ext, strict=strict, scores={})
    miss = sb._zero_claim_row(
        claim_f1=cf1,
        claim_f1_strict=cf1s,
        gold=gold,
        reason="no_submit",
        subcategory="extract",
    )
    miss.update(
        {
            "category": "bom",
            "subcategory": "extract",
            "case_id": "c-miss",
            "run_id": "r2",
        }
    )
    suite = sb.aggregate([hit, miss])["by_suite"]["bom/extract"]
    assert suite["micro_n_gold"] == 2
    assert suite["macro_f1"] == statistics.mean([1.0, 0.0])
