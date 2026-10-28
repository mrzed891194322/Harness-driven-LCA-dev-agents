"""Candidate-set hit and fabrication rate for mapping predictions.

PCFBench Task3 headline is exact-match top-1 of the chosen process name against
``expected.options`` (see README). ``item_id`` is an optional harness key for
multi-item gold only — never a scoring gate. A singleton gold pairs with a
singleton (or sole selectable) prediction by position / process_name even when
``item_id`` differs (e.g. pred uses case id while gold keeps ``m1``).

The closed candidate set comes from the expected file. A selection hits when
``process_id`` / ``provider_id`` is in that set, or when ``process_name`` /
``provider_name`` equals a candidate name (case-folded, whitespace collapsed).
Anything else that names a process is a fabrication. Exact match against
``options`` and ``banned_substring`` hits are reported beside the hit rate.
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


def _pred_item_list(pred: dict[str, Any]) -> list[dict[str, Any]]:
    raw = pred.get("items")
    if isinstance(raw, list) and raw:
        return [item for item in raw if isinstance(item, dict)]
    # Flat single-answer payload (process_name at top level).
    if isinstance(pred, dict) and _has_selection(pred) and not raw:
        return [pred]
    return []


def _align_pairs(
    gold_list: list[dict[str, Any]],
    pred_list: list[dict[str, Any]],
) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Pair each gold item with a prediction.

    - Prefer shared ``item_id`` when present on both sides.
    - Singleton fallback (PCFBench Task3 is one process per case): when there is
      exactly one gold item and either exactly one pred item or exactly one pred
      item with a process/provider selection, pair them regardless of ``item_id``.
    - Multi-item gold without an id match stays unmatched (``{}`` → abstained only
      if that pred truly has no selection elsewhere under that id).
    """
    pred_by_id: dict[str, dict[str, Any]] = {}
    for item in pred_list:
        key = item.get("item_id")
        if key is not None and str(key).strip():
            pred_by_id[str(key)] = item

    selectable = [item for item in pred_list if _has_selection(item)]
    singleton = len(gold_list) == 1 and (
        len(pred_list) == 1 or len(selectable) == 1
    )

    pairs: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for gold in gold_list:
        item_id = str(gold.get("item_id") or "m1")
        chosen = pred_by_id.get(item_id)
        if chosen is None and singleton:
            if len(selectable) == 1:
                chosen = selectable[0]
            elif len(pred_list) == 1:
                chosen = pred_list[0]
        pairs.append((item_id, gold, chosen or {}))
    return pairs


def score_mapping(expected: dict[str, Any], pred: dict[str, Any]) -> dict[str, Any]:
    # candidates may be absent: fall back to union of item.options (PCFBench shape).
    raw_candidates = list(expected.get("candidates") or [])
    if not raw_candidates:
        for item in expected.get("items") or []:
            if isinstance(item, dict):
                raw_candidates.extend(list(item.get("options") or []))
        if not raw_candidates and expected.get("options"):
            raw_candidates = list(expected.get("options") or [])
    if not raw_candidates and "candidates" not in expected and not expected.get("items"):
        # Still allow options-only expected_output from raw PCFBench.
        if expected.get("options"):
            raw_candidates = list(expected["options"])
        else:
            raise ValueError("expected mapping 缺少 candidates/options（封闭候选集）")

    names, ids = candidate_index(raw_candidates)
    gold_list = [item for item in (expected.get("items") or []) if isinstance(item, dict)]
    if not gold_list and expected.get("options"):
        # Raw PCFBench expected_output: synthesize one gold row.
        gold_list = [
            {
                "item_id": "m1",
                "options": list(expected.get("options") or []),
                "banned_substring": expected.get("banned_substring"),
            }
        ]
    pred_list = _pred_item_list(pred)

    rows: list[dict[str, Any]] = []
    for item_id, gold, chosen in _align_pairs(gold_list, pred_list):
        options = list(gold.get("options") or expected.get("options") or [])
        banned_raw = gold.get("banned_substring")
        if banned_raw is None:
            banned_raw = expected.get("banned_substring")
        if isinstance(banned_raw, str):
            banned = [banned_raw] if banned_raw.strip() else []
        elif isinstance(banned_raw, list):
            banned = list(banned_raw)
        else:
            banned = []
        if not _has_selection(chosen):
            outcome = "abstained"
        elif _in_set(chosen, names, ids):
            outcome = "candidate_hit"
        else:
            outcome = "fabricated"
        exact = _exact_match(chosen, options) if options else outcome == "candidate_hit"
        rows.append(
            {
                "item_id": item_id,
                "outcome": outcome,
                "exact_match": exact,
                "banned_violation": _banned(chosen, banned),
                "pred_item_id": chosen.get("item_id"),
                "process_name": next(iter(_selected_names(chosen)), None),
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
        "top1": _rate(exact, n_items),  # PCFBench Task3 headline alias
        "banned_violations": banned_n,
        "banned_violation_rate": _rate(banned_n, n_items),
        "abstained": abstained,
        "align": "singleton_process_name"
        if len(gold_list) == 1
        else "item_id",
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
