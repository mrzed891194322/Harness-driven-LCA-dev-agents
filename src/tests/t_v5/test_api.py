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


def test_gui_start_of_revise_uses_saved_revise_plan(monkeypatch, v5_root):
    client, svc = _client(monkeypatch, v5_root)
    make_node(v5_root, "r", produces=[{"spec": "paragraph", "path": "r/p.md"}])
    write_yaml(v5_root / "harness/workflows/revise-lca.yaml",
               {"id": "revise-lca", "nodes": ["r"], "plan_file": "revise_plan.md", "revise_of": "full-lca"})
    saved = {"content": ""}
    monkeypatch.setattr(app_module, "read_plan_document", lambda root, workflow=None: dict(saved))
    gui = {"workflow": "revise-lca", "subject": "原研究对象", "functional_unit": "1 L"}
    r = client.post("/api/workflow/start", json=gui)
    assert r.status_code == 400 and "修订计划为空" in r.json()["detail"]
    saved["content"] = "# 修订\n- 改运输\n"
    r = client.post("/api/workflow/start", json=gui)
    assert r.status_code == 200, r.text
    svc.wait(10)
    plan = v5_root / "workspace/artifacts/plan/revise_plan.md"
    assert plan.read_text(encoding="utf-8") == "# 修订\n- 改运输\n"
    wf = next(w for w in client.get("/api/v5/workflows").json()["workflows"] if w["id"] == "revise-lca")
    assert wf["plan_file"] == "revise_plan.md"


def test_preview_is_read_only_injection(monkeypatch, v5_root):
    client, svc = _client(monkeypatch, v5_root)
    before = sorted(str(p) for p in v5_root.rglob("*"))
    r = client.get("/api/v5/preview", params={"workflow": "full-lca"})
    assert r.status_code == 200, r.text
    node = r.json()["nodes"][0]
    assert node["id"] == "a" and {a["role"] for a in node["agents"]} == {"executor", "reviewer"}
    ex = next(a for a in node["agents"] if a["role"] == "executor")
    assert "<plan>" in ex["user"] and "deliverable_paragraph" in ex["user"] and ex["system"].strip()
    assert sorted(str(p) for p in v5_root.rglob("*")) == before  # no side effects
    assert client.get("/api/v5/preview", params={"workflow": "nope"}).status_code == 400


def test_agent_model_setting_applies_at_run_start(monkeypatch, v5_root):
    from backend.v5 import agent_models
    from backend.v5.config import load_workflow

    client, svc = _client(monkeypatch, v5_root)
    r = client.post("/api/v5/agent-models", json={"node": "a", "role": "executor", "model": "p/m1", "thinking": "high"})
    assert r.status_code == 200, r.text
    assert client.post("/api/v5/agent-models", json={"node": "a", "role": "boss"}).status_code == 400
    assert client.post("/api/v5/agent-models", json={"node": "a", "role": "executor", "thinking": "max"}).status_code == 400
    assert agent_models.settings_file(v5_root).is_file()
    _, nodes = load_workflow(v5_root, "full-lca")
    a = agent_models.apply(nodes, agent_models.load(v5_root))[0]
    assert a.agents["executor"].model == "p/m1" and a.agents["executor"].thinking == "high"
    assert a.agents["reviewer"].model == nodes[0].agents["reviewer"].model
    card = client.get("/api/v5/workflows").json()["workflows"][0]["details"][0]["agents"]["executor"]
    assert card["model_source"] == "gui" and card["gui_model"] == "p/m1"
    client.post("/api/v5/agent-models", json={"node": "a", "role": "executor"})
    assert agent_models.load(v5_root) == {}
