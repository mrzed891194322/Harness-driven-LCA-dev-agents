"""Hermetic tests for GET /api/harness/injection."""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.core.agents import injection, spec_mcp as spec_mcp_host
from backend.core.runtime.capabilities import base_capabilities
from backend.core.runtime.launch_spec import build_session_launch_spec
from backend.core.workflow.config.loader import load_workflow
from tests.support.minimal_workflow import write_minimal_workflow


def _launch_for_preview(root: Path):
    path = root / "harness" / "workflows" / "LCA-main.yaml"
    workflow = load_workflow(path, project_root=root, capabilities=base_capabilities())
    bundle = workflow.bundles["s1.executor"]
    stage = workflow.stage_by_id(bundle.stage_id)
    assignment = workflow.assignments["s1.executor"]
    with tempfile.TemporaryDirectory(prefix="injection-preview-") as tmp:
        workspace = Path(tmp) / "workspace"
        workspace.mkdir()
        key = Path(tmp) / "spec_mcp.key"
        key.write_bytes(b"k" * 64)
        original_ensure = spec_mcp_host.ensure_key
        spec_mcp_host.ensure_key = lambda _root: key  # type: ignore[method-assign]
        try:
            return build_session_launch_spec(
                workflow,
                bundle,
                project_root=root,
                workspace_root=workspace,
                worker="pi",
                model="default",
                stage=stage,
                assignment=assignment,
                run_id="preview",
                attempt=1,
                session_key="preview",
                run_context={"run_id": "preview"},
            )
        finally:
            spec_mcp_host.ensure_key = original_ensure


def test_injection_detail_layers_hash_and_no_workspace_writes(tmp_path: Path) -> None:
    root = tmp_path / "project"
    write_minimal_workflow(root, workflow_id="whole-lca", filename="workflows/LCA-main.yaml")
    workspace = root / "workspace"
    local = root / ".local"
    workspace.mkdir(parents=True)
    local.mkdir(parents=True)
    marker_ws = workspace / ".injection-marker"
    marker_local = local / ".injection-marker"
    marker_ws.write_text("mark\n", encoding="utf-8")
    marker_local.write_text("mark\n", encoding="utf-8")
    time.sleep(0.1)

    with patch("backend.api.app.PROJECT_ROOT", root):
        client = TestClient(app)
        response = client.get(
            "/api/harness/injection",
            params={
                "workflow": "LCA-main",
                "stage": "s1",
                "assignment": "s1.executor",
            },
        )
    assert response.status_code == 200
    body = response.json()
    for key in ("rules", "mcp", "knowledge"):
        rows = body.get(key) or []
        assert rows, key
        assert all(row.get("layer") for row in rows)

    launch = _launch_for_preview(root)
    intended = injection.build_intended(launch)
    assert (body.get("planned") or {}).get("system_prompt_hash") == intended.get("system_prompt_hash")

    for marker in (marker_ws, marker_local):
        result = subprocess.run(
            ["find", str(marker.parent), "-newer", str(marker)],
            capture_output=True,
            text=True,
            check=False,
        )
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        assert lines == [], f"unexpected writes under {marker.parent}: {lines}"


def test_injection_bad_workflow_returns_422_with_errors(tmp_path: Path) -> None:
    root = tmp_path / "project"
    workflows = root / "harness" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "broken.yaml").write_text("id: broken\nstages: [not-a-mapping]\n", encoding="utf-8")
    with patch("backend.api.app.PROJECT_ROOT", root):
        response = TestClient(app).get("/api/harness/injection", params={"workflow": "broken"})
    assert response.status_code == 422
    detail = response.json().get("detail") or {}
    errors = detail.get("errors") if isinstance(detail, dict) else None
    assert errors and isinstance(errors, list)
