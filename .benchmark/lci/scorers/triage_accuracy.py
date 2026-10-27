#!/usr/bin/env python3
"""Triage accuracy for PCFBench task2 (should_map binary).

Truth: {"should_map": bool, "candidate_name"?: str}
Pred:  {"should_map": bool, "confidence"?: float, "candidate_name"?: str, "rationale"?: str}

Primary metric: accuracy. Also reports precision/recall/F1/ECE when applicable.
CLI: python3 triage_accuracy.py <truth.json> <pred.json>  → JSON on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _as_decision(obj: dict[str, Any], *, fallback_name: str = "case") -> dict[str, Any] | None:
    if "should_map" not in obj:
        return None
    name = str(obj.get("candidate_name") or obj.get("name") or fallback_name).strip()
    out: dict[str, Any] = {
        "candidate_name": name or fallback_name,
        "should_map": bool(obj["should_map"]),
    }
    conf = obj.get("confidence")
    if conf is not None and isinstance(conf, (int, float)):
        out["confidence"] = float(conf)
    return out


def score_triage(gold: dict[str, Any], pred: dict[str, Any]) -> dict[str, Any]:
    """Score one case (single decision) or list-shaped payloads."""
    if isinstance(gold.get("decisions"), list) or isinstance(pred.get("decisions"), list):
        g_list = gold.get("decisions") or []
        p_list = pred.get("decisions") or []
    else:
        g_one = _as_decision(gold)
        p_one = _as_decision(pred, fallback_name=str(gold.get("candidate_name") or "case"))
        if g_one is None:
            return {"error": "truth_missing_should_map", "accuracy": None}
        if p_one is None:
            return {"error": "pred_missing_should_map", "accuracy": 0.0, "total_evaluated": 0}
        g_list, p_list = [g_one], [p_one]

    gt_map = {
        str(gt.get("candidate_name") or "").lower().strip(): bool(gt["should_map"])
        for gt in g_list
        if isinstance(gt, dict) and "should_map" in gt and gt.get("candidate_name") is not None
    }
    # if truth used fallback single name
    if not gt_map and len(g_list) == 1 and "should_map" in g_list[0]:
        n = str(g_list[0].get("candidate_name") or "case").lower().strip()
        gt_map[n] = bool(g_list[0]["should_map"])

    tp = fp = tn = fn = total = 0
    conf_pairs: list[tuple[float, bool]] = []
    for pred_row in p_list:
        if not isinstance(pred_row, dict) or "should_map" not in pred_row:
            continue
        name = str(pred_row.get("candidate_name") or pred_row.get("name") or "").lower().strip()
        if name not in gt_map:
            # single-case fallback: if only one gt, accept any name
            if len(gt_map) == 1:
                name = next(iter(gt_map))
            else:
                continue
        g_val = gt_map[name]
        p_bool = bool(pred_row["should_map"])
        total += 1
        if p_bool and g_val:
            tp += 1
        elif p_bool and not g_val:
            fp += 1
        elif not p_bool and not g_val:
            tn += 1
        else:
            fn += 1
        conf = pred_row.get("confidence")
        if conf is not None and isinstance(conf, (int, float)):
            conf_pairs.append((float(conf), p_bool == g_val))

    if total == 0:
        return {
            "total_evaluated": 0,
            "accuracy": 0.0,
            "f1": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "ece": None,
        }

    accuracy = (tp + tn) / total
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    ece = None
    if conf_pairs:
        num_bins = 10
        bin_counts = [0] * num_bins
        bin_correct = [0] * num_bins
        bin_conf_sum = [0.0] * num_bins
        for conf, correct in conf_pairs:
            clamped = min(max(conf, 0.0), 1.0)
            b_idx = min(int(clamped * num_bins), num_bins - 1)
            bin_counts[b_idx] += 1
            bin_conf_sum[b_idx] += clamped
            if correct:
                bin_correct[b_idx] += 1
        weighted_err = 0.0
        n = len(conf_pairs)
        for i in range(num_bins):
            if bin_counts[i] > 0:
                acc_i = bin_correct[i] / bin_counts[i]
                conf_i = bin_conf_sum[i] / bin_counts[i]
                weighted_err += (bin_counts[i] / n) * abs(acc_i - conf_i)
        ece = round(weighted_err, 4)

    return {
        "total_evaluated": total,
        "accuracy": round(accuracy, 4),
        "f1": round(f1, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "ece": ece,
        "correct": bool(accuracy == 1.0 and total == 1),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score triage should_map accuracy")
    p.add_argument("truth")
    p.add_argument("pred")
    args = p.parse_args(argv)
    gold = json.loads(Path(args.truth).read_text(encoding="utf-8"))
    pred = json.loads(Path(args.pred).read_text(encoding="utf-8"))
    print(json.dumps(score_triage(gold, pred), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
