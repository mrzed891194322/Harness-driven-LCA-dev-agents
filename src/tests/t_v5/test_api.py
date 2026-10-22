"""v5 API routes with a temp-project V5Service (no real workspace, no pi)."""
from __future__ import annotations

from fastapi.testclient import TestClient

import backend.api.app as app_module
from backend.v5.service import V5Service
from tests.t_v5.conftest import make_node, write_yaml
from tests.t_v5.fake_driver import FakeDriver


def _client(monkeypatch, root):
    make_node(root, "a", produces=[{"spec": "paragraph", "path": "a/p.md"}])
    write_yaml(root / "harness/workflows/orchestrations/full-lca.yaml", {"id": "full-lca", "nodes": ["a"]})
    svc = V5Service(root, driver_factory=lambda r: FakeDriver())
    monkeypatch.setattr(app_module, "_v5_service", svc)
    return TestClient(app_module.app), svc


def test_start_status_feedback_and_old_resume(monkeypatch, v5_root):
    client, svc = _client(monkeypatch, v5_root)
    assert client.get("/api/v5/workflows").json()["workflows"][0]["id"] == "full-lca"
    r = client.post("/api/workflow/start", json={"workflow": "full-lca", "plan": "# 计划\n"})
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
    write_yaml(v5_root / "harness/workflows/orchestrations/revise-lca.yaml",
               {"id": "revise-lca", "nodes": ["r"], "plan_file": "revise_plan.md", "start_rev": "next"})
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
    monkeypatch.setattr(app_module, "_saved_plan_text", lambda wf: "# 保存的计划 XYZ\n")
    before = sorted(str(p) for p in v5_root.rglob("*"))
    r = client.get("/api/v5/preview", params={"workflow": "full-lca"})
    assert r.status_code == 200, r.text
    node = r.json()["nodes"][0]
    assert node["id"] == "a" and {a["agent"] for a in node["agents"]} == {"executor", "reviewer"}
    ex = next(a for a in node["agents"] if a["agent"] == "executor")
    assert "<plan>" in ex["user"] and "deliverable_paragraph" in ex["user"] and ex["system"].strip()
    assert "保存的计划 XYZ" in ex["user"] and r.json()["plan_source"] == "saved"
    assert sorted(str(p) for p in v5_root.rglob("*")) == before  # no side effects
    assert client.get("/api/v5/preview", params={"workflow": "nope"}).status_code == 400


def test_agent_model_setting_applies_at_run_start(monkeypatch, v5_root):
    from backend.v5 import agent_models
    from backend.v5.config import load_workflow

    client, svc = _client(monkeypatch, v5_root)
    r = client.post("/api/v5/agent-models", json={"node": "a", "agent": "executor", "model": "p/m1", "thinking": "high"})
    assert r.status_code == 200, r.text
    assert client.post("/api/v5/agent-models", json={"node": "a", "agent": "boss"}).status_code == 400
    assert client.post("/api/v5/agent-models", json={"node": "a", "agent": "executor", "thinking": "max"}).status_code == 400
    assert agent_models.settings_file(v5_root).is_file()
    _, nodes = load_workflow(v5_root, "full-lca")
    a = agent_models.apply(nodes, agent_models.load(v5_root))[0]
    assert a.agents["executor"].model == "p/m1" and a.agents["executor"].thinking == "high"
    assert a.agents["reviewer"].model == nodes[0].agents["reviewer"].model
    card = client.get("/api/v5/workflows").json()["workflows"][0]["details"][0]["agents"]["executor"]
    assert card["model_source"] == "gui" and card["gui_model"] == "p/m1"
    client.post("/api/v5/agent-models", json={"node": "a", "agent": "executor"})
    assert agent_models.load(v5_root) == {}


def test_preflight_checks_every_configured_model(monkeypatch, v5_root):
    """Default model + each distinct per-agent model gets its own preflight (temp project, fake runtime)."""
    from types import SimpleNamespace

    import backend.core.runtime.model_profiles as mp
    from backend.v5.pi_driver import PiDriver

    seen: list[str] = []

    class D(PiDriver):
        def __init__(self):
            self.root = v5_root
            self.model = SimpleNamespace(profile_id="p/default", parameters={})

        def _preflight_once(self, workspace, attempt=1, model=None):
            seen.append(model.profile_id)
            return "boom" if model.profile_id == "p/bad" else None

    monkeypatch.setattr(mp, "resolve_model_profile", lambda ref, project_root=None: SimpleNamespace(profile_id=ref, parameters={}))
    d = D()
    assert d.preflight(v5_root, models=["p/a", "p/default", "p/a", ""]) is None
    assert seen == ["p/default", "p/a"]
    seen.clear()
    assert d.preflight(v5_root, models=["p/bad"]) == "p/bad：boom"


def test_runner_passes_agent_models_to_preflight(monkeypatch, v5_root):
    from backend.v5 import agent_models

    client, svc = _client(monkeypatch, v5_root)
    agent_models.save(v5_root, "a", "reviewer", model="p/rev")
    got = {}

    class F(FakeDriver):
        def preflight(self, ws, models=None):
            got["models"] = models
            return None

    svc.driver_factory = lambda r: F()
    assert client.post("/api/workflow/start", json={"workflow": "full-lca", "plan": "# 计划\n"}).status_code == 200
    svc.wait(10)
    assert got["models"] == ["p/rev"]


def test_old_runs_feed_from_v5_session_files(monkeypatch, v5_root):
    """599ed0a /runs feed: progress text + activity built read-only from events and the live pi session file."""
    import json as _json

    client, svc = _client(monkeypatch, v5_root)
    assert client.post("/api/workflow/start", json={"workflow": "full-lca", "plan": "# 计划\n"}).status_code == 200
    svc.wait(10)
    ws = v5_root / "workspace"
    sess = ws / "tmp" / "pi-v5" / "a.executor" / "session.jsonl"
    sess.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"type": "message", "timestamp": "2999-01-01T00:00:00Z", "message": {"role": "assistant", "model": "m-1",
         "content": [{"type": "text", "text": "开始"}, {"type": "toolCall", "id": "c1", "name": "read", "arguments": {"path": "x.md"}}]}},
        {"type": "message", "timestamp": "2999-01-01T00:00:01Z", "message": {"role": "toolResult", "toolCallId": "c1",
         "toolName": "read", "isError": True, "content": [{"type": "text", "text": "not found"}]}},
    ]
    sess.write_text("\n".join(_json.dumps(r) for r in rows), encoding="utf-8")
    before = sorted(str(p) for p in v5_root.rglob("*"))
    p = client.get("/api/workflow/progress").json()
    assert p["status"] == "completed" and p["reset"] is True and p["epoch"] == p["run_id"] and p["workflow"] == "full-lca"
    assert "[a(executor#1)-m_1-" in p["text"] and "→ read x.md" in p["text"] and "✗ read: not found" in p["text"]
    again = client.get("/api/workflow/progress", params={"offset": p["offset"], "epoch": p["epoch"]}).json()
    assert again["text"] == "" and again["reset"] is False
    act = client.get("/api/workflow/activity", params={"run_id": p["run_id"]}).json()["events"]
    assert [e["kind"] for e in act if e.get("tool") == "read"] == ["tool_call", "tool_result"]
    wl = client.get("/api/workflows").json()["workflows"]
    assert wl[0]["id"] == "full-lca" and wl[0]["mode"] == "main"
    assert sorted(str(p) for p in v5_root.rglob("*")) == before
