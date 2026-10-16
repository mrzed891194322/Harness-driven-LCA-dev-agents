from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from backend.core.workflow.main import main
from backend.core.workflow.persistence.manifest import manifest_path
from backend.core.workflow.persistence.workflow_snapshot import (
    evidence_workflow_path,
    local_workflow_path,
)
from tests.conftest import PROJECT_ROOT, WORKFLOWS


def test_write_workflow_snapshot_on_new_run(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wf = WORKFLOWS / "LCA-main.yaml"
    expected = wf.read_text(encoding="utf-8")
    run_id = "a" * 32

    with (
        patch("backend.core.workflow.main.uuid.uuid4") as uid,
        patch("backend.core.workflow.main.run_workflow", return_value={"status": "completed"}),
    ):
        uid.return_value.hex = run_id
        code = main(
            [
                "--workflow",
                str(wf),
                "--worker",
                "pi",
                "--project-root",
                str(PROJECT_ROOT),
                "--workspace",
                str(workspace),
            ]
        )
    assert code == 0
    assert evidence_workflow_path(workspace, run_id).read_text(encoding="utf-8") == expected
    assert local_workflow_path(PROJECT_ROOT, run_id).read_text(encoding="utf-8") == expected
    rel = evidence_workflow_path(workspace, run_id).relative_to(workspace).as_posix()
    assert manifest_path(workspace).read_text(encoding="utf-8").find(rel) >= 0
    local_workflow_path(PROJECT_ROOT, run_id).unlink()
    (local_workflow_path(PROJECT_ROOT, run_id).parent).rmdir()
