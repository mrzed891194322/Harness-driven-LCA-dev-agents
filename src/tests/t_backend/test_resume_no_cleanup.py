from __future__ import annotations

import json
from pathlib import Path

from backend.services.executor_console import run_pre_workflow_console
from backend.core.workflow.workspace.index import register_attempt
from backend.core.workflow.workspace.layout import attempts
from backend.services.resume_plan import reused_accepted_attempts


def test_resume_pre_workflow_does_not_delete_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    marker = workspace / "runs" / "02-inventory-extraction" / "executor-1" / "handoff.json"
    marker.parent.mkdir(parents=True)
    marker.write_text("{}", encoding="utf-8")
    chunks = list(
        run_pre_workflow_console(
            "resume-lca",
            document_values=[],
            source_text="",
            ref_upload_file=None,
        )
    )
    assert chunks[-1][1] == "Finished"
    assert marker.is_file()


def test_resume_preview_lists_reused_accepted_attempts(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    stage = "02-inventory-extraction"
    accepted = {
        "stage": stage,
        "executor": f"runs/{stage}/executor-1",
        "reviewer": f"runs/{stage}/reviewer-1",
        "accepted_at": "t",
        "fingerprint": "abc",
    }
    path = workspace / "runs" / stage / "accepted.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(accepted), encoding="utf-8")
    reused = reused_accepted_attempts(workspace, "03-dataset-mapping")
    assert reused and reused[0]["executor"].endswith("executor-1")


def test_resume_attempt_number_continues_from_workspace(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    stage = "03-dataset-mapping"
    register_attempt(ws, stage, "executor", 1, "old", origin="whole-lca")
    register_attempt(ws, stage, "executor", 2, "old", origin="whole-lca")
    register_attempt(ws, stage, "reviser", 1, "old", origin="resume-lca")
    rows = attempts(ws, stage)
    assert max(int(r["attempt"]) for r in rows if r["role"] == "executor") == 2
    assert any(r["role"] == "reviser" and r["attempt"] == 1 for r in rows)
