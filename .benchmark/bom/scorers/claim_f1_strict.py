"""Strict PCFBench-aligned claim F1 (value+unit tuples only, official matcher)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_OFFICIAL_PATH = Path(__file__).resolve().parent / "pcfbench_official" / "extraction.py"
_spec = importlib.util.spec_from_file_location(
    "pcfbench_official_extraction", _OFFICIAL_PATH
)
assert _spec is not None and _spec.loader is not None
official = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(official)

STRICT_UNIT_TABLE_VERSION = (
    "pcfbench@1b93a6899eb9:upstream/extraction.py+unit_normalization.py (vendored strict)"
)


def _vu_tuples(doc: dict[str, Any]) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for claim in doc.get("claims") or []:
        value = claim.get("value")
        unit = claim.get("unit")
        if value is not None and unit:
            out.append((float(value), str(unit)))
    return out


def _per_case_f1(*, matched: int, n_gold: int, n_pred: int) -> tuple[float, float, float]:
    precision = matched / n_pred if n_pred else 0.0
    recall = matched / n_gold if n_gold else 0.0
    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def zero_pred_scores(
    gold: dict[str, Any] | None = None,
    *,
    reason: str = "no_artifact",
) -> dict[str, Any]:
    n_gold = len(_vu_tuples(gold or {}))
    return {
        "match": "official_exact_tuple",
        "mode": "strict",
        "n_gold": n_gold,
        "n_pred": 0,
        "matched": 0,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "hallucination_rate": 0.0,
        "reason": reason,
        "unit_table": STRICT_UNIT_TABLE_VERSION,
    }


def score_claims(gold: dict[str, Any], pred: dict[str, Any]) -> dict[str, Any]:
    gt = _vu_tuples(gold)
    pr = _vu_tuples(pred)
    matches, _, _ = official._match_extraction_claims(pr, gt)
    matched = len(matches)
    n_gold, n_pred = len(gt), len(pr)
    precision, recall, f1 = _per_case_f1(
        matched=matched, n_gold=n_gold, n_pred=n_pred
    )
    hallucination_rate = (n_pred - matched) / n_pred if n_pred else 0.0
    return {
        "match": "official_exact_tuple",
        "mode": "strict",
        "n_gold": n_gold,
        "n_pred": n_pred,
        "matched": matched,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "hallucination_rate": hallucination_rate,
        "unit_table": STRICT_UNIT_TABLE_VERSION,
    }


def micro_f1_from_rows(rows: list[dict[str, Any]]) -> float:
    matched = sum(int(r["matched"]) for r in rows)
    n_pred = sum(int(r["n_pred"]) for r in rows)
    n_gold = sum(int(r["n_gold"]) for r in rows)
    return official.run_claim_f1([matched], [n_pred], [n_gold])
