"""Claim F1 for extraction-style claims.

Match key is the canonical ``(value, unit)`` tuple when both sides have them.
Unit table + scale factors follow PCFBench
``pcfbench/scoring/unit_normalization.py`` (watershed-climate/pcfbench@1b93a6899eb9).
Predicted units also try PCFBench ``_unit_candidates`` prose cleanups before
lookup. Matching stays exact_tuple_one_to_one (each gold/pred used at most once).

Text-only claims (no value) match on normalized text instead.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# Stamp for score_batch summary notes (upstream file + commit).
UNIT_TABLE_VERSION = "pcfbench@1b93a6899eb9:pcfbench/scoring/unit_normalization.py"

_UNICODE_REPLACEMENTS: dict[str, str] = {
    "²": "2",
    "³": "3",
    "₂": "2",
    "₃": "3",
    "⁻": "-",
    "·": "/",
}

# lookup key (via _canonical_key) → (canonical unit, scale for value)
UNIT_NORMALIZATION: dict[str, tuple[str, float]] = {
    # --- Percent ---
    "%": ("percent", 1.0),
    "percent": ("percent", 1.0),
    "mass%": ("percent", 1.0),
    "wt%": ("percent", 1.0),
    "weight%": ("percent", 1.0),
    "%mass": ("percent", 1.0),
    "%wt": ("percent", 1.0),
    "percentreduction": ("percent", 1.0),
    # --- Mass ratio ---
    "kg/kg": ("kg/kg", 1.0),
    "g/kg": ("kg/kg", 0.001),
    "gr/kg": ("kg/kg", 0.001),
    "grams/kilogram": ("kg/kg", 0.001),
    "grams/kg": ("kg/kg", 0.001),
    # --- Energy intensity ---
    "mj/kg": ("mj/kg", 1.0),
    "gj/t": ("mj/kg", 1.0),
    "gj/tonne": ("mj/kg", 1.0),
    "kwh/kg": ("kwh/kg", 1.0),
    "kw.hr/kg": ("kwh/kg", 1.0),
    "kwhr/kg": ("kwh/kg", 1.0),
    "kwh/ton": ("kwh/kg", 0.001),
    "kwh/tonne": ("kwh/kg", 0.001),
    "btu/lb": ("btu/lb", 1.0),
    "btu/lbm": ("btu/lb", 1.0),
    # --- kgCO2e per kg ---
    "kgco2e/kg": ("kgco2e/kg", 1.0),
    "kgco2eq/kg": ("kgco2e/kg", 1.0),
    "kgco2eqperkg": ("kgco2e/kg", 1.0),
    "kgco2eperkg": ("kgco2e/kg", 1.0),
    "kgco2eq/1kg": ("kgco2e/kg", 1.0),
    "kgco2/kg": ("kgco2e/kg", 1.0),
    "kgco2e/tonne": ("kgco2e/kg", 0.001),
    "kgco2eq/tonne": ("kgco2e/kg", 0.001),
    "kgco2e/t": ("kgco2e/kg", 0.001),
    "tonnesco2e/tonne": ("kgco2e/kg", 1.0),
    "tco2e/tonne": ("kgco2e/kg", 1.0),
    "tco2e/t": ("kgco2e/kg", 1.0),
    # --- kgCO2e per m² ---
    "kgco2e/m2": ("kgco2e/m2", 1.0),
    "kgco2eq/m2": ("kgco2e/m2", 1.0),
    # --- kgCO2e per FU ---
    "kgco2e/fu": ("kgco2e/fu", 1.0),
    "kgco2eq/fu": ("kgco2e/fu", 1.0),
}

# Absolute-mass aliases seen in our import gold (not in upstream table).
# Keep as pass-through-friendly scales so g ↔ kg still match if both sides
# use these forms; does not invent cross-family energy conversions.
_EXTRA_MASS: dict[str, tuple[str, float]] = {
    "kg": ("kg", 1.0),
    "g": ("kg", 0.001),
    "gram": ("kg", 0.001),
    "grams": ("kg", 0.001),
    "lb": ("kg", 0.453592),
    "lbs": ("kg", 0.453592),
    "lbm": ("kg", 0.453592),
    "t": ("kg", 1000.0),
    "tonne": ("kg", 1000.0),
    "ton": ("kg", 1000.0),
}


def _canonical_key(unit: str) -> str:
    s = unit.strip().lower()
    for old, new in _UNICODE_REPLACEMENTS.items():
        s = s.replace(old, new)
    s = s.replace(" per ", "/")
    s = s.replace("-eq.", "eq").replace("-eq", "eq")
    s = s.replace(" eq.", "eq").replace(" eq", "eq")
    s = s.replace("eq.", "eq")
    s = s.replace(".", "")
    s = s.replace("-", "")
    s = re.sub(r"\s+", "", s)
    return s


def unit_candidates(unit: str) -> list[str]:
    """PCFBench pred-unit prose cleanups (comma / paren / first token)."""
    if not unit:
        return [unit]
    seen: set[str] = set()
    out: list[str] = []
    for candidate in (
        unit,
        unit.split(",", 1)[0].strip(),
        re.split(r"\s*\(", unit, 1)[0].strip(),
        unit.split()[0] if unit.split() else unit,
    ):
        if candidate and candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def normalize_value_and_unit(value: float, unit: str) -> tuple[float, str]:
    """Return ``(scaled_value, canonical_unit)``. Unknown → (value, key)."""
    key = _canonical_key(unit)
    if key in UNIT_NORMALIZATION:
        canonical, scale = UNIT_NORMALIZATION[key]
        return value * scale, canonical
    if key in _EXTRA_MASS:
        canonical, scale = _EXTRA_MASS[key]
        return value * scale, canonical
    return value, key


def normalize_unit(unit: str) -> str:
    _, canonical = normalize_value_and_unit(1.0, unit)
    return canonical


def norm_text(text: str) -> str:
    return " ".join(text.casefold().split())


def claim_key(
    claim: dict[str, Any],
    *,
    prefer_units: set[str] | None = None,
) -> tuple[Any, ...]:
    """Canonical match key. When prefer_units is set (pred side), try unit_candidates."""
    value = claim.get("value")
    unit = claim.get("unit")
    if value is not None and unit:
        raw = str(unit)
        chosen: tuple[float, str] | None = None
        if prefer_units is not None:
            for cand in unit_candidates(raw):
                cv, cu = normalize_value_and_unit(float(value), cand)
                if cu in prefer_units:
                    chosen = (cv, cu)
                    break
        if chosen is None:
            chosen = normalize_value_and_unit(float(value), raw)
        cv, cu = chosen
        return ("vu", round(cv, 6), cu)
    return ("text", norm_text(str(claim.get("text") or "")))


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def zero_pred_scores(
    gold: dict[str, Any] | None = None,
    *,
    reason: str = "no_artifact",
) -> dict[str, Any]:
    """Stuck / no_submit / missing claims.json: count as F1=0 (not skipped)."""
    n_gold = len((gold or {}).get("claims") or [])
    return {
        "match": "exact_tuple_one_to_one",
        "n_gold": n_gold,
        "n_pred": 0,
        "matched": 0,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "hallucination_rate": 0.0,
        "reason": reason,
        "unit_table": UNIT_TABLE_VERSION,
    }


def score_claims(gold: dict[str, Any], pred: dict[str, Any]) -> dict[str, Any]:
    """One-to-one multiset F1. Both-empty agreement scores F1 = 1."""
    gold_claims = gold.get("claims") or []
    pred_claims = pred.get("claims") or []
    gold_keys = [claim_key(c) for c in gold_claims]
    prefer = {k[2] for k in gold_keys if k[0] == "vu"}
    pred_keys = [claim_key(c, prefer_units=prefer) for c in pred_claims]
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
        "unit_table": UNIT_TABLE_VERSION,
    }


def is_abstain(doc: dict[str, Any]) -> bool:
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
