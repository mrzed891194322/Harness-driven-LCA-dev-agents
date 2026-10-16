"""Unit tests for three-layer compose (global -> stage -> agent)."""

from __future__ import annotations

import pytest

from backend.core.workflow.config.compose import (
    E_COMPOSE_PLAIN_LIST,
    E_COMPOSE_REMOVE_LOCKED,
    E_COMPOSE_REMOVE_MISSING,
    E_COMPOSE_UNKNOWN,
    ComposeError,
    compose_component_list,
)


def test_plain_list_at_stage_raises() -> None:
    with pytest.raises(ComposeError) as exc:
        compose_component_list(
            component="rules",
            global_ids=["a"],
            stage_decl=["x"],
            assignment_decl=None,
            known_ids={"a", "x"},
        )
    assert exc.value.code == E_COMPOSE_PLAIN_LIST


def test_remove_locked_raises() -> None:
    with pytest.raises(ComposeError) as exc:
        compose_component_list(
            component="rules",
            global_ids=["a", "b"],
            stage_decl={"remove": ["a"]},
            assignment_decl=None,
            known_ids={"a", "b"},
            locked_ids={"a"},
        )
    assert exc.value.code == E_COMPOSE_REMOVE_LOCKED


def test_remove_missing_raises() -> None:
    with pytest.raises(ComposeError) as exc:
        compose_component_list(
            component="rules",
            global_ids=["a"],
            stage_decl={"remove": ["missing"]},
            assignment_decl=None,
            known_ids={"a"},
        )
    assert exc.value.code == E_COMPOSE_REMOVE_MISSING


def test_unknown_add_raises() -> None:
    with pytest.raises(ComposeError) as exc:
        compose_component_list(
            component="rules",
            global_ids=["a"],
            stage_decl={"add": ["nope"]},
            assignment_decl=None,
            known_ids={"a"},
        )
    assert exc.value.code == E_COMPOSE_UNKNOWN


def test_duplicate_add_keeps_first_layer() -> None:
    result = compose_component_list(
        component="rules",
        global_ids=["a"],
        stage_decl={"add": ["b"]},
        assignment_decl={"add": ["a"]},
        known_ids={"a", "b"},
    )
    assert result.ids == ["a", "b"]
    assert result.provenance["a"] == "global"
    assert any("duplicate" in n for n in result.notes)
