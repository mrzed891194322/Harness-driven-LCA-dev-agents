"""Local workflow copies under .local/harness/workflows (or test override)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.core.workflow.main import main
from backend.core.workflow.persistence.manifest import manifest_path
from backend.core.workflow.persistence.workflow_snapshot import (
    evidence_workflow_path,
    read_workflow_snapshot_text,
)
from backend.services.local_workflows import (
    effective_workflow_path,
    local_workflow_path,
    local_workflows_root,
    recorded_default_sha_path,
    restore_default,
    sync_workflow,
    unified_diff_text,
)
from backend.services.project_paths import MAIN_WORKFLOW_NAME, PROJECT_ROOT
from tests.conftest import PROJECT_ROOT as REPO
from tests.conftest import WORKFLOWS


def test_pytest_uses_isolated_local_workflows_dir() -> None:
    root = local_workflows_root(REPO)
    real = (REPO / ".local" / "harness" / "workflows").resolve()
    assert root != real
    assert os.environ.get("LCA_LOCAL_WORKFLOWS_DIR")


def test_copy_and_record_sha(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    local = tmp_path / "local-wf"
    monkeypatch.setenv("LCA_LOCAL_WORKFLOWS_DIR", str(local))
    item = sync_workflow(REPO, MAIN_WORKFLOW_NAME)
    assert item.local_exists
    assert local_workflow_path(REPO, MAIN_WORKFLOW_NAME).is_file()
    recorded = recorded_default_sha_path(REPO, MAIN_WORKFLOW_NAME).read_text(encoding="utf-8").strip()
    assert recorded == item.default_sha256


def test_auto_update_when_local_matches_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    local = tmp_path / "local-wf"
    monkeypatch.setenv("LCA_LOCAL_WORKFLOWS_DIR", str(local))
    sync_workflow(REPO, MAIN_WORKFLOW_NAME)
    default = WORKFLOWS / MAIN_WORKFLOW_NAME
    text = default.read_text(encoding="utf-8")
    default.write_text(text + "\n# tracked bump\n", encoding="utf-8")
    try:
        item = sync_workflow(REPO, MAIN_WORKFLOW_NAME)
        assert item.auto_updated
        assert "# tracked bump" in local_workflow_path(REPO, MAIN_WORKFLOW_NAME).read_text(encoding="utf-8")
    finally:
        default.write_text(text, encoding="utf-8")
        sync_workflow(REPO, MAIN_WORKFLOW_NAME)


def test_keep_modified_when_default_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    local = tmp_path / "local-wf"
    monkeypatch.setenv("LCA_LOCAL_WORKFLOWS_DIR", str(local))
    sync_workflow(REPO, MAIN_WORKFLOW_NAME)
    local_file = local_workflow_path(REPO, MAIN_WORKFLOW_NAME)
    local_file.write_text(local_file.read_text(encoding="utf-8") + "\nuser:\n  tweak: true\n", encoding="utf-8")
    default = WORKFLOWS / MAIN_WORKFLOW_NAME
    text = default.read_text(encoding="utf-8")
    default.write_text(text + "\n# tracked bump\n", encoding="utf-8")
    try:
        item = sync_workflow(REPO, MAIN_WORKFLOW_NAME)
        assert item.default_updated
        assert item.modified
        assert "user:" in local_file.read_text(encoding="utf-8")
        assert "# tracked bump" not in local_file.read_text(encoding="utf-8")
    finally:
        default.write_text(text, encoding="utf-8")
        restore_default(REPO, MAIN_WORKFLOW_NAME)


def test_restore_and_diff_endpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    local = tmp_path / "local-wf"
    monkeypatch.setenv("LCA_LOCAL_WORKFLOWS_DIR", str(local))
    sync_workflow(REPO, MAIN_WORKFLOW_NAME)
    local_file = local_workflow_path(REPO, MAIN_WORKFLOW_NAME)
    local_file.write_text("id: user-only\n", encoding="utf-8")
    diff = unified_diff_text(REPO, MAIN_WORKFLOW_NAME)
    assert "user-only" in diff or "local/" in diff
    client = TestClient(app)
    response = client.get(f"/api/harness/workflows/{MAIN_WORKFLOW_NAME}/diff")
    assert response.status_code == 200
    assert "diff" in response.json()
    restore = client.post(f"/api/harness/workflows/{MAIN_WORKFLOW_NAME}/restore-default")
    assert restore.status_code == 200
    assert "tweak" not in local_file.read_text(encoding="utf-8") or "registry:" in local_file.read_text(encoding="utf-8")


def test_resume_prefers_snapshot_over_mutated_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    local = tmp_path / "local-wf"
    monkeypatch.setenv("LCA_LOCAL_WORKFLOWS_DIR", str(local))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    sync_workflow(REPO, MAIN_WORKFLOW_NAME)
    run_id = "b" * 32
    snap_text = (WORKFLOWS / MAIN_WORKFLOW_NAME).read_text(encoding="utf-8")
    evidence_workflow_path(workspace, run_id).parent.mkdir(parents=True, exist_ok=True)
    evidence_workflow_path(workspace, run_id).write_text(snap_text, encoding="utf-8")
    local_workflow_path(REPO, MAIN_WORKFLOW_NAME).write_text("id: mutated-local\n", encoding="utf-8")

    assert read_workflow_snapshot_text(REPO, workspace, run_id) == snap_text
    assert read_workflow_snapshot_text(REPO, workspace, run_id) != local_workflow_path(
        REPO, MAIN_WORKFLOW_NAME
    ).read_text(encoding="utf-8")

    documents: list[object] = []
    from backend.core.workflow.config.loader import load_workflow as real_load

    def _spy(path, **kwargs):
        documents.append(kwargs.get("document"))
        return real_load(path, **kwargs)

    state = {
        "run_id": run_id,
        "runtime_version": 4,
        "status": "running",
        "in_flight": True,
        "next_action": "advance",
    }
    with (
        patch("backend.core.workflow.main.load_workflow", side_effect=_spy),
        patch("backend.core.workflow.main.open_store") as store_ctx,
        patch("backend.core.workflow.main.workspace_lock"),
        patch("backend.core.workflow.main.run_workflow", return_value={"status": "completed"}),
    ):
        store = store_ctx.return_value.__enter__.return_value
        store.load.return_value = state
        code = main(
            [
                "--workflow",
                str(WORKFLOWS / MAIN_WORKFLOW_NAME),
                "--worker",
                "pi",
                "--project-root",
                str(REPO),
                "--workspace",
                str(workspace),
                "--resume",
                run_id,
            ]
        )
    assert code == 0
    assert documents
    assert isinstance(documents[0], dict)
    assert documents[0].get("registry") is not None
    assert documents[0].get("id") != "mutated-local"
