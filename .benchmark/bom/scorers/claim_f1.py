"""Claim F1 for extraction-style claims.

Match key is the canonical ``(value, unit)`` tuple when both sides have them.
Units in ``UNIT_SCALE`` are scaled (g → kg, kWh → MJ, mass% → percent) and the
value is rounded to 6 decimal places. Each gold claim and each prediction is
used at most once. Unmatched predictions are hallucinations.

Text-only claims (no value) match on normalized text instead.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# canonical unit, multiply the raw value by this factor
UNIT_SCALE: dict[str, tuple[str, float]] = {
    "kg": ("kg", 1.0),
    "g": ("kg", 0.001),
    "lb": ("kg", 0.453592),
    "lbs": ("kg", 0.453592),
    "t": ("kg", 1000.0),
    "kg/kg": ("kg/kg", 1.0),
    "g/kg": ("kg/kg", 0.001),
    "percent": ("percent", 1.0),
    "%": ("percent", 1.0),
    "wt%": ("percent", 1.0),
    "wt.%": ("percent", 1.0),
    "mass%": ("percent", 1.0),
    "mj": ("mj", 1.0),
    "mj/kg": ("mj/kg", 1.0),
    "kwh": ("mj", 3.6),
    "kwh/kg": ("mj/kg", 3.6),
}


def norm_unit(unit: str) -> str:
    return unit.strip().casefold().replace(" ", "").replace("·", "").replace("％", "%")


def norm_text(text: str) -> str:
    return " ".join(text.casefold().split())


def claim_key(claim: dict[str, Any]) -> tuple[Any, ...]:
    value = claim.get("value")
    unit = claim.get("unit")
    if value is not None and unit:
        raw_unit = norm_unit(str(unit))
        canonical, factor = UNIT_SCALE.get(raw_unit, (raw_unit, 1.0))
        return ("vu", round(float(value) * factor, 6), canonical)
    return ("text", norm_text(str(claim.get("text") or "")))


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def score_claims(gold: dict[str, Any], pred: dict[str, Any]) -> dict[str, Any]:
    """One-to-one multiset F1. Both-empty agreement scores F1 = 1."""
    gold_keys = [claim_key(c) for c in gold.get("claims") or []]
    pred_keys = [claim_key(c) for c in pred.get("claims") or []]
    gold_counts, pred_counts = Counter(gold_keys), Counter(pred_keys)
    matched = sum(min(gold_counts[k], pred_counts[k]) for k in gold_counts)
    n_gold, n_pred = len(gold_keys), len(pred_keys)
    if n_gold == 0 and n_pred == 0:
        precision = recall = f1 = 1.0
    else:
        precision = matched / n_pred if n_pred else 0.0
        recall = matched / n_gold if n_gold else 0.0
        f1 = _f1(precision, recall)
    hallucination_rate = (n_pred - matched) / n_pred if n_pred else 0.0
    return {
        "match": "exact_tuple_one_to_one",
        "n_gold": n_gold,
        "n_pred": n_pred,
        "matched": matched,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "hallucination_rate": hallucination_rate,
    }


def is_abstain(doc: dict[str, Any]) -> bool:
    """Abstain only when there are no claims. A non-empty list is an answer."""
    return not (doc.get("claims") or [])


def score_abstention(gold: dict[str, Any], pred: dict[str, Any]) -> dict[str, Any]:
    expected = is_abstain(gold)
    predicted = is_abstain(pred)
    return {
        "expected_abstain": expected,
        "predicted_abstain": predicted,
        "abstention_correct": bool(expected and predicted),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="对两份 claim set 计算 F1")
    parser.add_argument("gold", type=Path)
    parser.add_argument("pred", type=Path)
    args = parser.parse_args(argv)
    gold = json.loads(args.gold.read_text(encoding="utf-8"))
    pred = json.loads(args.pred.read_text(encoding="utf-8"))
    json.dump(score_claims(gold, pred), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
