"""Deterministic component-set F1 for PCFBench task1 (product decomposition).

Official PCFBench Task 1 uses an LLM judge (Gemini) to form compositional match
groups, then computes P/R/F1. This scorer is an offline stand-in: normalize
component strings and greedily 1-1 exact-match on the normalized forms.
Notes in the score payload flag ``judge=deterministic_norm`` so results are not
confused with the paper's judge-aligned F1.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

UNIT_TABLE = "deterministic_norm@v1"


def norm_component(value: str) -> str:
    text = " ".join(str(value).casefold().split())
    text = re.sub(r"[\[\](){},;]+", " ", text)
    return " ".join(text.split())


def _as_list(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("components")
    if raw is None and isinstance(payload.get("expected_output"), dict):
        raw = payload["expected_output"].get("components")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            for key in ("name", "component", "text"):
                if isinstance(item.get(key), str) and item[key].strip():
                    out.append(item[key].strip())
                    break
    return out


def zero_pred_scores(gold: dict[str, Any] | None, *, reason: str) -> dict[str, Any]:
    n_gold = len(_as_list(gold or {}))
    return {
        "f1": 0.0,
        "precision": 0.0,
        "recall": 0.0,
        "n_gold": n_gold,
        "n_pred": 0,
        "matched": 0,
        "judge": "deterministic_norm",
        "unit_table": UNIT_TABLE,
        "reason": reason,
    }


def score_decomposition(gold: dict[str, Any], pred: dict[str, Any]) -> dict[str, Any]:
    gold_raw = _as_list(gold)
    pred_raw = _as_list(pred)
    gold_norm = [norm_component(x) for x in gold_raw]
    pred_norm = [norm_component(x) for x in pred_raw]
    used: set[int] = set()
    matched = 0
    pairs: list[dict[str, str]] = []
    for gi, g in enumerate(gold_norm):
        if not g:
            continue
        hit = None
        for pi, p in enumerate(pred_norm):
            if pi in used or not p:
                continue
            if p == g:
                hit = pi
                break
        if hit is not None:
            used.add(hit)
            matched += 1
            pairs.append({"gold": gold_raw[gi], "pred": pred_raw[hit]})
    n_gold = len([x for x in gold_norm if x])
    n_pred = len([x for x in pred_norm if x])
    precision = matched / n_pred if n_pred else 0.0
    recall = matched / n_gold if n_gold else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "f1": round(f1, 6),
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "n_gold": n_gold,
        "n_pred": n_pred,
        "matched": matched,
        "pairs": pairs,
        "judge": "deterministic_norm",
        "unit_table": UNIT_TABLE,
        "note": "Offline stand-in; official PCFBench Task1 uses LLM-judge match groups.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score decomposition component F1")
    p.add_argument("truth", type=Path)
    p.add_argument("pred", type=Path)
    args = p.parse_args(argv)
    gold = json.loads(args.truth.read_text(encoding="utf-8"))
    pred = json.loads(args.pred.read_text(encoding="utf-8"))
    print(json.dumps(score_decomposition(gold, pred), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
