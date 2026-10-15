"""全量运行开跑前：先清 openLCA，成功后才清 workspace；旧 outputs/ records/ 一并删除。"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import backend.services.workspace_clean as clean_main


def _targets(workspace: Path) -> list[dict]:
    cfg = next(t for t in clean_main.CLEAN_TARGETS if t["name"] == "workspace")
    return [{**cfg, "path": workspace, "gitignore": workspace / ".gitignore"}]


def _seed(workspace: Path) -> None:
    for rel in ("outputs/LCI/a.json", "records/handoffs/h.json", "runs/x/y.json"):
        p = workspace / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}", encoding="utf-8")


def test_whole_lca_preset_order():
    assert clean_main.CLEAN_PRESETS["whole-lca"] == ["openlca", "workspace"]
    assert "workspace" not in clean_main.CLEAN_PRESETS["revise-lca"]


def test_whole_lca_removes_legacy_outputs_and_records(tmp_path: Path):
    ws = tmp_path / "workspace"
    _seed(ws)
    with (
        patch.object(clean_main, "CLEAN_TARGETS", _targets(ws)),
        patch.object(clean_main, "PROJECT_ROOT", tmp_path),
        patch.object(clean_main, "run_openlca_clean", return_value=(True, "ok", {})),
    ):
        assert clean_main.run_clean(yes=True, preset="whole-lca") == 0
    assert not (ws / "outputs" / "LCI" / "a.json").exists()
    assert not (ws / "records" / "handoffs" / "h.json").exists()
    assert not (ws / "runs" / "x" / "y.json").exists()


def test_workspace_untouched_when_openlca_clean_fails(tmp_path: Path):
    ws = tmp_path / "workspace"
    _seed(ws)
    with (
        patch.object(clean_main, "CLEAN_TARGETS", _targets(ws)),
        patch.object(clean_main, "PROJECT_ROOT", tmp_path),
        patch.object(clean_main, "run_openlca_clean", return_value=(False, "timeout", {})),
    ):
        assert clean_main.run_clean(yes=True, preset="whole-lca") != 0
    assert (ws / "outputs" / "LCI" / "a.json").exists()
    assert (ws / "records" / "handoffs" / "h.json").exists()
