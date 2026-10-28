"""PCFBench Task3 mapping scorer: process_name top-1; item_id is not a gate."""

from pathlib import Path
import importlib.util

REPO = Path(__file__).resolve().parents[3]
PATH = REPO / ".benchmark/lci/scorers/fabrication_rate.py"


def _mod():
    spec = importlib.util.spec_from_file_location("fabrication_rate", PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _gold(option: str = "polylactic acid, granulate"):
    return {
        "candidates": [{"id": "opt-1", "name": option}],
        "items": [
            {
                "item_id": "m1",
                "options": [option],
                "material_name": f"market for {option}",
            }
        ],
    }


def test_nv_style_case_id_still_hits():
    """Pred item_id = case id (≠ m1) with correct process_name → hit, not abstained."""
    m = _mod()
    option = "polylactic acid, granulate"
    pred = {
        "items": [
            {
                "item_id": "map-0839ee31959cef350db13489",
                "process_name": option,
            }
        ]
    }
    s = m.score_mapping(_gold(option), pred)
    assert s["abstained"] == 0
    assert s["candidate_hits"] == 1
    assert s["exact_matches"] == 1
    assert s["exact_match_rate"] == 1.0
    assert s["top1"] == 1.0
    assert s["items"][0]["outcome"] == "candidate_hit"
    assert s["align"] == "singleton_process_name"


def test_no_selection_is_abstained():
    m = _mod()
    pred = {"items": [{"item_id": "map-x", "process_name": None}]}
    s = m.score_mapping(_gold(), pred)
    assert s["abstained"] == 1
    assert s["exact_match_rate"] == 0.0


def test_wrong_name_fabricated():
    m = _mod()
    pred = {"items": [{"item_id": "map-x", "process_name": "totally wrong process"}]}
    s = m.score_mapping(_gold(), pred)
    assert s["items"][0]["outcome"] == "fabricated"
    assert s["exact_matches"] == 0


def test_matching_item_id_still_works():
    m = _mod()
    option = "polylactic acid, granulate"
    pred = {"items": [{"item_id": "m1", "process_name": option}]}
    s = m.score_mapping(_gold(option), pred)
    assert s["candidate_hits"] == 1 and s["top1"] == 1.0


def test_multi_item_still_by_item_id():
    m = _mod()
    gold = {
        "candidates": [
            {"id": "a", "name": "alpha"},
            {"id": "b", "name": "beta"},
        ],
        "items": [
            {"item_id": "m1", "options": ["alpha"]},
            {"item_id": "m2", "options": ["beta"]},
        ],
    }
    # Wrong ids on pred → no singleton fallback → both abstained
    pred = {
        "items": [
            {"item_id": "case-a", "process_name": "alpha"},
            {"item_id": "case-b", "process_name": "beta"},
        ]
    }
    s = m.score_mapping(gold, pred)
    assert s["align"] == "item_id"
    assert s["abstained"] == 2
    # Correct ids → hits
    pred2 = {
        "items": [
            {"item_id": "m1", "process_name": "alpha"},
            {"item_id": "m2", "process_name": "beta"},
        ]
    }
    s2 = m.score_mapping(gold, pred2)
    assert s2["candidate_hits"] == 2 and s2["top1"] == 1.0
