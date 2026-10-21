"""v5 API routes with a temp-project V5Service (no real workspace, no pi)."""
from __future__ import annotations

from fastapi.testclient import TestClient

import backend.api.app as app_module
from backend.v5.service import V5Service
from tests.t_v5.conftest import make_node, write_yaml
from tests.t_v5.fake_driver import FakeDriver


def _client(monkeypatch, root):
    make_node(root, "a", produces=[{"spec": "paragraph", "path": "a/p.md"}])
    write_yaml(root / "harness/workflows/full-lca.yaml", {"id": "full-lca", "nodes": ["a"]})
    svc = V5Service(root, driver_factory=lambda r: FakeDriver())
    monkeypatch.setattr(app_module, "_v5_service", svc)
    return TestClient(app_module.app), svc


def test_start_status_feedback_and_old_resume(monkeypatch, v5_root):
    client, svc = _client(monkeypatch, v5_root)
    assert client.get("/api/v5/workflows").json()["workflows"][0]["id"] == "full-lca"
    r = client.post("/api/workflow/start", json={"task": "whole-lca", "plan": "# 计划\n"})
    assert r.status_code == 200, r.text
    svc.wait(10)
    st = client.get("/api/v5/status").json()
    assert st["status"] == "completed" and st["nodes"][0]["id"] == "a"
    assert client.get("/api/v5/nodes/a/feedback/1").status_code == 404
    assert client.get("/api/v5/nodes/..%2Fx/feedback/1").status_code in (400, 404)
    assert client.post("/api/workflow/resume", json={"run_id": "x", "from_stage": "y"}).status_code == 404
    assert client.post("/api/workflow/start", json={"workflow": "full-lca", "plan": " "}).status_code == 400
    assert client.post("/api/workflow/stop").status_code == 409
