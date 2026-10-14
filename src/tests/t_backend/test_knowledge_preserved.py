"""Pre-run never clears knowledge; plan writes are atomic; inputs are add-only."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from backend.services import executor_console
from backend.services.plan_form import save_references, write_text_atomic
from backend.services.workspace_clean import CLEAN_PRESETS


def test_presets_never_include_knowledge():
    assert CLEAN_PRESETS == {"whole-lca": ["openlca", "workspace"], "revise-lca": ["openlca"]}


def test_pre_run_clean_command_has_no_knowledge_target():
    for task in ("whole-lca", "revise-lca"):
        command = executor_console.clean_dir_command(preset=task)
        assert "knowledge" not in command


def test_write_text_atomic_creates_then_replaces(tmp_path: Path):
    path = tmp_path / "plan" / "main_plan.md"
    write_text_atomic(path, "v1")
    assert path.read_text(encoding="utf-8") == "v1"
    write_text_atomic(path, "v2")
    assert path.read_text(encoding="utf-8") == "v2"
    assert [p.name for p in path.parent.iterdir()] == ["main_plan.md"]


def test_write_text_atomic_keeps_old_file_on_failure(tmp_path: Path):
    path = tmp_path / "revise_plan.md"
    write_text_atomic(path, "old")
    with patch.object(os, "replace", side_effect=OSError("boom")):
        try:
            write_text_atomic(path, "new")
        except OSError:
            pass
    assert path.read_text(encoding="utf-8") == "old"
    assert [p.name for p in tmp_path.iterdir()] == ["revise_plan.md"]


def test_reference_sync_is_add_only(tmp_path: Path):
    inputs = tmp_path / "harness" / "knowledge" / "inputs"
    inputs.mkdir(parents=True)
    (inputs / "keep.md").write_text("keep", encoding="utf-8")
    (inputs / "same.md").write_text("old", encoding="utf-8")
    save_references(tmp_path, [("same.md", b"new"), ("added.md", b"add")])
    assert (inputs / "keep.md").read_text(encoding="utf-8") == "keep"
    assert (inputs / "same.md").read_bytes() == b"new"
    assert (inputs / "added.md").read_bytes() == b"add"
