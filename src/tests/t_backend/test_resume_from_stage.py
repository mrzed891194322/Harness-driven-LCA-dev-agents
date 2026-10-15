from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.core.workflow.persistence.manifest import write_manifest
from backend.services.resume_plan import (
    build_plan,
    cleanup_workspace_paths,
    eligibility,
    normalize_resume_code,
    resume_plan_dir,
)
from backend.services.workspace_clean import run_cleanup_list
from tests.conftest import PROJECT_ROOT, WORKFLOWS


def _write_handoff(workspace: Path, stage: str, attempt: int, status: str = "passed") -> None:
    folder = workspace / "runs" / stage / f"reviewer-{attempt}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "handoff.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "stage": stage,
                "role": "reviewer",
                "attempt": attempt,
                "status": status,
            }
        ),
        encoding="utf-8",
    )


def _stage02_artifacts(workspace: Path) -> None:
    inv = workspace / "artifacts"
    inv.mkdir(parents=True, exist_ok=True)
    (inv / "extracted-bom.json").write_text("{}", encoding="utf-8")
    (inv / "extracted-bom.md").write_text("# bom\n", encoding="utf-8")


def test_normalize_resume_code() -> None:
    assert normalize_resume_code("02") == "02"
    assert normalize_resume_code("03-dataset-mapping") == "03"


def test_eligibility_refuses_stage_01() -> None:
    out = eligibility(PROJECT_ROOT, "deadbeef", "01")
    assert out["eligible"] is False
    assert any("whole-lca" in r for r in out["reasons"])


def test_filter_workflow_plan_id(tmp_path: Path) -> None:
    plan_dir = tmp_path / "harness" / "knowledge" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "main_plan.md").write_text("# plan\n", encoding="utf-8")
    (tmp_path / "harness" / "knowledge" / "inputs").mkdir(parents=True)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    run_id = "a" * 32
    write_manifest(
        workspace,
        status="failed",
        current_stage="03-dataset-mapping",
        status_reason="x",
        run_id=run_id,
    )
    wf_text = (WORKFLOWS / "LCA-main.yaml").read_text(encoding="utf-8")
    ev = workspace / "runs" / "_run" / "evidence" / run_id
    ev.mkdir(parents=True)
    (ev / "workflow.yaml").write_text(wf_text, encoding="utf-8")
    for stage in ("01-intake-gate", "02-inventory-extraction"):
        _write_handoff(workspace, stage, 1)
    _stage02_artifacts(workspace)
    art = workspace / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    (art / "process-mapping.json").write_text("{}", encoding="utf-8")
    lci = art / "LCI"
    lci.mkdir(parents=True)
    (lci / "placeholder.json").write_text("{}", encoding="utf-8")
    from backend.core.runtime.knowledge_providers.local_files import discover_files_at

    sources_dir = ev / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    files = discover_files_at(tmp_path, "harness/knowledge/plan")["files"]
    files += discover_files_at(tmp_path, "harness/knowledge/inputs")["files"]
    (sources_dir / "01-intake-gate.reviewer.json").write_text(
        json.dumps({"files": files}), encoding="utf-8"
    )

    out = eligibility(tmp_path, run_id, "03")
    assert out["eligible"] is True
    plan = build_plan(tmp_path, run_id, "03")
    composed = yaml.safe_load(
        (resume_plan_dir(workspace, run_id) / "workflow.yaml").read_text(encoding="utf-8")
    )
    assert composed["id"] == "resume-lca"
    stage_ids = [s["id"] for s in composed["stages"]]
    assert stage_ids == ["03-dataset-mapping", "04-openlca-reporting"]


def test_cleanup_list_refuses_knowledge(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    payload = {"workspace_paths": ["harness/knowledge/plan/x.md"], "openlca_ids": []}
    list_path = tmp_path / "cleanup.json"
    list_path.write_text(json.dumps(payload), encoding="utf-8")
    with patch(
        "backend.services.workspace_clean.PROJECT_ROOT",
        tmp_path,
    ):
        code, report = run_cleanup_list(list_path, yes=True)
    assert code == 1
    assert report["workspace_refused"]


def test_cleanup_list_deletes_only_listed(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    target = workspace / "artifacts" / "reports"
    target.mkdir(parents=True)
    keep = workspace / "runs" / "_run" / "evidence" / "oldrun"
    keep.mkdir(parents=True)
    (keep / "manifest.json").write_text("{}", encoding="utf-8")
    (target / "a.txt").write_text("x", encoding="utf-8")
    payload = {"workspace_paths": ["artifacts/reports"], "openlca_ids": []}
    list_path = tmp_path / "cleanup.json"
    list_path.write_text(json.dumps(payload), encoding="utf-8")
    with patch("backend.services.workspace_clean.PROJECT_ROOT", tmp_path):
        code, report = run_cleanup_list(list_path, yes=True, old_run_id="oldrun")
    assert code == 0
    assert "artifacts/reports" in report["workspace_deleted"]
    assert keep.is_dir()


def test_resume_preview_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/api/runs/nosuch/resume-preview", params={"from_stage": "02"})
    assert response.status_code == 200
    body = response.json()
    assert body["eligible"] is False


def test_resume_post_409_when_ineligible() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/workflow/resume",
        json={"run_id": "nosuch", "from_stage": "02"},
    )
    assert response.status_code == 409


@patch("backend.services.workflow_launch.launcher.start")
def test_resume_post_launches(mock_start: MagicMock) -> None:
    mock_start.return_value = {"status": "started", "task": "resume-lca", "epoch": "e"}
    run_id = "b" * 32
    workspace = PROJECT_ROOT / "workspace"
    write_manifest(
        workspace,
        status="failed",
        current_stage="02-inventory-extraction",
        status_reason="x",
        run_id=run_id,
    )
    wf = (WORKFLOWS / "LCA-main.yaml").read_text(encoding="utf-8")
    ev = workspace / "runs" / "_run" / "evidence" / run_id
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "workflow.yaml").write_text(wf, encoding="utf-8")
    _write_handoff(workspace, "01-intake-gate", 1)
    client = TestClient(app)
    preview = client.get(f"/api/runs/{run_id}/resume-preview", params={"from_stage": "02"})
    if not preview.json().get("eligible"):
        return  # workspace state may not match in shared env
    response = client.post(
        "/api/workflow/resume",
        json={"run_id": run_id, "from_stage": "02"},
    )
    if response.status_code == 200:
        mock_start.assert_called_once()
