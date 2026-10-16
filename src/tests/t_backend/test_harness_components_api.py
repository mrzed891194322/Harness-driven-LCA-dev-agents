"""Workflow editor reads components from the backend scan, not YAML `registry:`."""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from backend.api.app import app

REPO = Path(__file__).resolve().parents[3]


def test_components_endpoint_lists_discovered_components() -> None:
    data = TestClient(app).get("/api/harness/components").json()
    assert "check/inventory" in data["host_action"]
    assert data["host_action"]["check/inventory"]["command"]
    assert "control_openlca" in data["mcp"]
    assert data["rules"]["write-boundary"].startswith("harness/prompts/")
    assert isinstance(data["knowledge"], dict)


def test_shipped_workflows_have_no_registry() -> None:
    for name in ("LCA-main.yaml", "LCA-revise.yaml"):
        raw = yaml.safe_load((REPO / "harness" / "workflows" / name).read_text("utf-8"))
        assert "registry" not in raw


def test_frontend_does_not_read_yaml_registry() -> None:
    src = (REPO / "src/frontend/web/components/plan/workflow-yaml.ts").read_text("utf-8")
    assert "raw.registry" not in src
    assert "/api/harness/components" in src
