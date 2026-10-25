"""Candidate-set hit and fabrication rate for mapping predictions.

The closed candidate set comes from the expected file, not from the names the
model lists on its own deliverable. A selection hits when ``process_id`` or
``provider_id`` is in that set, or when ``process_name`` / ``provider_name``
equals a candidate name (case-folded, whitespace collapsed). Anything else
that names a process is a fabrication. Exact match against ``options`` and
``banned_substring`` hits are reported beside the hit rate; they do not
decide fabrication.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def norm_name(value: str) -> str:
    return " ".join(value.casefold().split())


def _add_candidate(names: set[str], ids: set[str], candidate: Any) -> None:
    if isinstance(candidate, str):
        text = candidate.strip()
        if text:
            names.add(norm_name(text))
        return
    if not isinstance(candidate, dict):
        return
    for key in ("name", "activity_name", "process_name"):
        if candidate.get(key):
            names.add(norm_name(str(candidate[key])))
    for key in ("id", "uuid", "activity_id", "process_id"):
        if candidate.get(key):
            ids.add(str(candidate[key]).strip().casefold())


def candidate_index(candidates: list[Any]) -> tuple[set[str], set[str]]:
    names: set[str] = set()
    ids: set[str] = set()
    for candidate in candidates:
        _add_candidate(names, ids, candidate)
    return names, ids


def _selected_names(item: dict[str, Any]) -> list[str]:
    found = []
    for key in ("process_name", "provider_name", "flow_name"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            found.append(norm_name(value))
    return found


def _selected_ids(item: dict[str, Any]) -> list[str]:
    found = []
    for key in ("process_id", "provider_id"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            found.append(value.strip().casefold())
    return found


def _in_set(item: dict[str, Any], names: set[str], ids: set[str]) -> bool:
    if any(name in names for name in _selected_names(item)):
        return True
    return any(uid in ids for uid in _selected_ids(item))


def _has_selection(item: dict[str, Any]) -> bool:
    return bool(_selected_names(item) or _selected_ids(item))


def _exact_match(item: dict[str, Any], options: list[Any]) -> bool:
    allowed = {norm_name(str(option)) for option in options if str(option).strip()}
    return any(name in allowed for name in _selected_names(item))


def _banned(item: dict[str, Any], banned: list[Any]) -> bool:
    needles = [
        norm_name(str(item_text)) for item_text in banned if str(item_text).strip()
    ]
    if not needles:
        return False
    haystacks = _selected_names(item)
    return any(needle in hay for hay in haystacks for needle in needles)


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def score_mapping(expected: dict[str, Any], pred: dict[str, Any]) -> dict[str, Any]:
    if "candidates" not in expected:
        raise ValueError("expected mapping 缺少 candidates（封闭候选集）")
    names, ids = candidate_index(list(expected.get("candidates") or []))
    gold_items = {str(item["item_id"]): item for item in expected.get("items") or []}
    pred_items = {str(item.get("item_id")): item for item in pred.get("items") or []}
    rows: list[dict[str, Any]] = []
    for item_id, gold in gold_items.items():
        chosen = pred_items.get(item_id) or {}
        options = list(gold.get("options") or [])
        banned = list(gold.get("banned_substring") or [])
        if not _has_selection(chosen):
            outcome = "abstained"
        elif _in_set(chosen, names, ids):
            outcome = "candidate_hit"
        else:
            outcome = "fabricated"
        rows.append(
            {
                "item_id": item_id,
                "outcome": outcome,
                "exact_match": _exact_match(chosen, options),
                "banned_violation": _banned(chosen, banned),
            }
        )
    n_items = len(rows)
    hits = sum(1 for row in rows if row["outcome"] == "candidate_hit")
    fabricated = sum(1 for row in rows if row["outcome"] == "fabricated")
    abstained = sum(1 for row in rows if row["outcome"] == "abstained")
    exact = sum(1 for row in rows if row["exact_match"])
    banned_n = sum(1 for row in rows if row["banned_violation"])
    return {
        "n_items": n_items,
        "candidate_hits": hits,
        "candidate_hit_rate": _rate(hits, n_items),
        "fabricated": fabricated,
        "fabrication_rate": _rate(fabricated, n_items),
        "exact_matches": exact,
        "exact_match_rate": _rate(exact, n_items),
        "banned_violations": banned_n,
        "banned_violation_rate": _rate(banned_n, n_items),
        "abstained": abstained,
        "items": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="候选集命中与编造率")
    parser.add_argument("expected", type=Path)
    parser.add_argument("pred", type=Path)
    args = parser.parse_args(argv)
    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    pred = json.loads(args.pred.read_text(encoding="utf-8"))
    json.dump(score_mapping(expected, pred), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
