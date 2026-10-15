"""Safety edges of resume-lca: cleanup list guards, openLCA journal-only deletes, input checks."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.core.runtime.hashing import sha256_file
from backend.services import resume_plan
from backend.services.workspace_clean import run_cleanup_list

PROJECT = "202606-harness-agent-LCA"


def _list(tmp_path: Path, paths, ids=()):
    path = tmp_path / "cleanup.json"
    path.write_text(json.dumps({"workspace_paths": list(paths), "openlca_ids": list(ids)}), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "rel",
    [".", "../outside", "tmp/../..", "runs/_run/orchestrator.sqlite",
     "runs/_run/resume/x", "runs/_run/evidence/oldrun"],
)
def test_cleanup_list_refuses_dangerous_paths(tmp_path: Path, rel: str):
    ws = tmp_path / "workspace"
    (ws / "runs" / "_run" / "evidence" / "oldrun").mkdir(parents=True)
    (ws / "runs" / "_run" / "orchestrator.sqlite").write_text("db", encoding="utf-8")
    (tmp_path / "outside").mkdir()
    with patch("backend.services.workspace_clean.PROJECT_ROOT", tmp_path):
        code, report = run_cleanup_list(_list(tmp_path, [rel]), yes=True, old_run_id="oldrun")
    assert code == 1
    assert report["workspace_refused"] and not report["workspace_deleted"]
    assert (ws / "runs" / "_run" / "orchestrator.sqlite").is_file()
    assert (ws / "runs" / "_run" / "evidence" / "oldrun").is_dir()
    assert (tmp_path / "outside").is_dir()


class _Client:
    def __init__(self, store):
        self.store = store
        self.deleted: list[str] = []

    def get(self, *_a, **_k):
        raise AssertionError("cleanup must not call full data/get")

    def get_descriptor(self, model_type, entity_id):
        return self.store.get(entity_id)

    def delete(self, ref):
        self.deleted.append(ref.id)


def _entity(entity_id, category):
    return SimpleNamespace(id=entity_id, name=entity_id, category=category,
                           to_ref=lambda: SimpleNamespace(id=entity_id))


def test_cleanup_list_openlca_deletes_only_listed_project_ids(tmp_path: Path):
    (tmp_path / "workspace").mkdir()
    client = _Client({
        "own": _entity("own", f"{PROJECT}/flows"),
        "foreign": _entity("foreign", "C:Manufacturing"),
        "unlisted": _entity("unlisted", f"{PROJECT}/flows"),
    })
    ids = [{"type": "Flow", "id": "own"}, {"type": "Flow", "id": "foreign"}]
    with (
        patch("backend.services.workspace_clean.PROJECT_ROOT", tmp_path),
        patch("harness.tools.shared.control_openlca.cleanup_service._target_category", return_value=PROJECT),
        patch("backend.services.diagnostics_service.openlca_endpoint", return_value=("127.0.0.1", 8080)),
        patch("harness.tools.shared.control_openlca.cleanup.connect_ipc", return_value=client),
        patch("harness.tools.shared.control_openlca.cleanup.close_ipc_client"),
    ):
        code, report = run_cleanup_list(_list(tmp_path, [], ids), yes=True)
    assert client.deleted == ["own"]
    assert report["openlca_deleted"] == 1
    assert any(item["id"] == "foreign" for item in report["openlca_skipped"])


def test_cleanup_list_openlca_dry_run_touches_nothing(tmp_path: Path):
    (tmp_path / "workspace").mkdir()
    with (
        patch("backend.services.workspace_clean.PROJECT_ROOT", tmp_path),
        patch("harness.tools.shared.control_openlca.cleanup.connect_ipc") as connect,
    ):
        code, report = run_cleanup_list(_list(tmp_path, [], [{"type": "Flow", "id": "own"}]), dry_run=True)
    assert code == 0 and not connect.called
    assert report["openlca_deleted"] == [{"type": "Flow", "id": "own"}]


def _sources(root: Path, run_id: str, files: dict[str, str]):
    folder = root / "workspace" / "runs" / "_run" / "evidence" / run_id / "sources"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "x.json").write_text(json.dumps({"files": [
        {"path": rel, "readable": True, "sha256": digest} for rel, digest in files.items()
    ]}), encoding="utf-8")


def test_inputs_check_detects_changed_and_added_files(tmp_path: Path):
    plan = tmp_path / "harness" / "knowledge" / "plan" / "main_plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("v1", encoding="utf-8")
    _sources(tmp_path, "r1", {"harness/knowledge/plan/main_plan.md": sha256_file(plan)})
    ws = tmp_path / "workspace"
    assert resume_plan._inputs_unchanged(tmp_path, ws, "r1", "03-dataset-mapping")[0]
    plan.write_text("v2", encoding="utf-8")
    ok, reasons = resume_plan._inputs_unchanged(tmp_path, ws, "r1", "03-dataset-mapping")
    assert not ok and "main_plan.md" in reasons[0]
    plan.write_text("v1", encoding="utf-8")
    extra = tmp_path / "harness" / "knowledge" / "inputs" / "new.md"
    extra.parent.mkdir(parents=True)
    extra.write_text("x", encoding="utf-8")
    ok, reasons = resume_plan._inputs_unchanged(tmp_path, ws, "r1", "03-dataset-mapping")
    assert not ok and "新增" in reasons[0]


def test_stage_04_requires_model_acceptance(tmp_path: Path):
    preview = resume_plan.eligibility(tmp_path, "r1", "04")
    assert not preview["eligible"]
    assert any("accepted[lca.model]" in r for r in preview["reasons"])


def test_cleanup_paths_include_records_for_later_stages(tmp_path: Path):
    ws = tmp_path / "workspace"
    for stage, role, attempt in (
        ("02-inventory-extraction", "reviewer", 1),
        ("03-dataset-mapping", "executor", 1),
        ("04-openlca-reporting", "executor", 1),
    ):
        folder = ws / "runs" / stage / f"{role}-{attempt}"
        folder.mkdir(parents=True)
        (folder / "handoff.json").write_text("{}", encoding="utf-8")
    journal = ws / "runs" / "04-openlca-reporting" / "executor-1" / "import-operations" / "operations"
    journal.mkdir(parents=True)
    paths = resume_plan.cleanup_workspace_paths(ws, "03-dataset-mapping")
    assert "runs/03-dataset-mapping/executor-1" in paths
    assert "runs/04-openlca-reporting/executor-1" in paths
    assert not any("02-inventory-extraction" in p for p in paths)
    assert "artifacts/LCI" in paths and "artifacts/lca_report.md" in paths
    assert not any(p.startswith("artifacts/extracted-bom") for p in paths)
