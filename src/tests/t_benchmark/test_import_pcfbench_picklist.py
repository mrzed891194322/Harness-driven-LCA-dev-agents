"""Tests for PCFBench import picklist alignment (T2/T3)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / ".benchmark" / "scripts"))

import import_pcfbench_cases as ipc  # noqa: E402


def test_load_ecoinvent_picklist_names_count() -> None:
    names = ipc.load_ecoinvent_picklist_names(REPO)
    assert len(names) >= 2000
    assert all(isinstance(n, str) and n for n in names[:10])


def test_triage_prompt_includes_full_picklist() -> None:
    names = ipc.load_ecoinvent_picklist_names(REPO)
    inp = {
        "market": {"name": "m", "description": "d"},
        "material_context_data": {"material_name": "root"},
    }
    prompt = ipc.pcfbench_triage_user_prompt(inp, picklist_names=names)
    assert "Ecoinvent activities:" in prompt
    assert prompt.count("\n") > 100
    assert names[0] in prompt
    assert names[-1] in prompt


def test_mapping_prompt_full_picklist_vs_small_options() -> None:
    full = ipc.load_ecoinvent_picklist_names(REPO)
    inp = {"material_name": "Steel sheet"}
    small = ["option-a", "option-b"]
    prompt_full = ipc.pcfbench_mapping_user_prompt(inp, options=full)
    prompt_small = ipc.pcfbench_mapping_user_prompt(inp, options=small)
    assert "Ecoinvent reference products:" in prompt_full
    assert len(prompt_full) > len(prompt_small) * 50
    assert full[0] in prompt_full
    assert "option-a" not in prompt_full or full[0] == "option-a"


def test_mapping_prompt_without_options_omits_block() -> None:
    inp = {"material_name": "x"}
    prompt = ipc.pcfbench_mapping_user_prompt(inp, options=None)
    assert "Ecoinvent reference products:" not in prompt
