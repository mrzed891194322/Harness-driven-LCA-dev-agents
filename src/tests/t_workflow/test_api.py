"""workflow API routes with a temp-project WorkflowService (no real workspace, no pi)."""
from __future__ import annotations

from fastapi.testclient import TestClient

import backend.api.app as app_module
from backend.workflow.service import WorkflowService
from tests.t_workflow.conftest import make_node, write_yaml, node_ref, spec_ref
from tests.t_workflow.fake_driver import FakeDriver


def _client(monkeypatch, root):
    make_node(root, "a", produces=[{"spec": spec_ref("paragraph"), "path": "a/p.md"}])
    write_yaml(root / "harness/workflows/orchestrations/full-lca.yaml", {"id": "full-lca", "nodes": [node_ref("a")]})
    svc = WorkflowService(root, driver_factory=lambda r: FakeDriver())
    monkeypatch.setattr(app_module, "_workflow_service", svc)
    return TestClient(app_module.app), svc


def test_start_status_feedback_and_old_resume(monkeypatch, wf_root):
    client, svc = _client(monkeypatch, wf_root)
    assert client.get("/api/workflow/workflows").json()["workflows"][0]["id"] == "full-lca"
    r = client.post("/api/workflow/start", json={"workflow": "full-lca", "plan": "# 计划\n"})
    assert r.status_code == 200, r.text
    svc.wait(10)
    st = client.get("/api/workflow/status").json()
    assert st["status"] == "completed" and st["nodes"][0]["id"] == "a"
    assert client.get("/api/workflow/nodes/a/feedback/1").status_code == 404
    assert client.get("/api/workflow/nodes/..%2Fx/feedback/1").status_code in (400, 404)
    assert client.post("/api/workflow/resume", json={"run_id": "x", "from_stage": "y"}).status_code == 422  # old body shape rejected
    assert client.post("/api/workflow/start", json={"workflow": "full-lca", "plan": " "}).status_code == 400
    assert client.post("/api/workflow/stop").status_code == 409


def test_gui_start_of_revise_uses_saved_revise_plan(monkeypatch, wf_root):
    client, svc = _client(monkeypatch, wf_root)
    make_node(wf_root, "r", produces=[{"spec": spec_ref("paragraph"), "path": "r/p.md"}])
    write_yaml(wf_root / "harness/workflows/orchestrations/revise-lca.yaml",
               {"id": "revise-lca", "nodes": [node_ref("r")], "plan_file": "revise_plan.md", "start_rev": "next"})
    saved = {"content": ""}
    monkeypatch.setattr(app_module, "read_plan_document", lambda root, workflow=None: dict(saved))
    gui = {"workflow": "revise-lca", "subject": "原研究对象", "functional_unit": "1 L"}
    r = client.post("/api/workflow/start", json=gui)
    assert r.status_code == 400 and "修订计划为空" in r.json()["detail"]
    saved["content"] = "# 修订\n- 改运输\n"
    r = client.post("/api/workflow/start", json=gui)
    assert r.status_code == 200, r.text
    svc.wait(10)
    plan = wf_root / "workspace/artifacts/plan/revise_plan.md"
    assert plan.read_text(encoding="utf-8") == "# 修订\n- 改运输\n"
    wf = next(w for w in client.get("/api/workflow/workflows").json()["workflows"] if w["id"] == "revise-lca")
    assert wf["plan_file"] == "revise_plan.md"


def test_preview_is_read_only_injection(monkeypatch, wf_root):
    client, svc = _client(monkeypatch, wf_root)
    monkeypatch.setattr(app_module, "_saved_plan_text", lambda wf: "# 保存的计划 XYZ\n")
    before = sorted(str(p) for p in wf_root.rglob("*"))
    r = client.get("/api/workflow/preview", params={"workflow": "full-lca"})
    assert r.status_code == 200, r.text
    node = r.json()["nodes"][0]
    assert node["id"] == "a" and {a["agent"] for a in node["agents"]} == {"executor", "reviewer"}
    ex = next(a for a in node["agents"] if a["agent"] == "executor")
    assert "<plan>" in ex["user"] and "deliverable_paragraph" in ex["user"] and ex["system"].strip()
    assert "保存的计划 XYZ" in ex["user"] and r.json()["plan_source"] == "saved"
    assert sorted(str(p) for p in wf_root.rglob("*")) == before  # no side effects
    assert client.get("/api/workflow/preview", params={"workflow": "nope"}).status_code == 400


def test_agent_model_setting_applies_at_run_start(monkeypatch, wf_root):
    from backend.workflow import agent_models
    from backend.workflow.config import load_workflow

    client, svc = _client(monkeypatch, wf_root)
    r = client.post("/api/workflow/agent-models", json={"node": "a", "agent": "executor", "model": "p/m1", "thinking": "high"})
    assert r.status_code == 200, r.text
    assert client.post("/api/workflow/agent-models", json={"node": "a", "agent": "boss"}).status_code == 400
    assert client.post("/api/workflow/agent-models", json={"node": "a", "agent": "executor", "thinking": "max"}).status_code == 400
    assert agent_models.settings_file(wf_root).is_file()
    _, nodes = load_workflow(wf_root, "full-lca")
    a = agent_models.apply(nodes, agent_models.load(wf_root))[0]
    assert a.agents["executor"].model == "p/m1" and a.agents["executor"].thinking == "high"
    assert a.agents["reviewer"].model == nodes[0].agents["reviewer"].model
    card = client.get("/api/workflow/workflows").json()["workflows"][0]["details"][0]["agents"]["executor"]
    assert card["model_source"] == "gui" and card["gui_model"] == "p/m1"
    client.post("/api/workflow/agent-models", json={"node": "a", "agent": "executor"})
    assert agent_models.load(wf_root) == {}


def test_preflight_checks_every_configured_model(monkeypatch, wf_root):
    """Default model + each distinct per-agent model gets its own preflight (temp project, fake runtime)."""
    from types import SimpleNamespace

    import backend.core.runtime.model_profiles as mp
    from backend.workflow.pi_driver import PiDriver

    seen: list[str] = []

    class D(PiDriver):
        def __init__(self):
            self.root = wf_root
            self.model = SimpleNamespace(profile_id="p/default", parameters={})

        def _preflight_once(self, workspace, attempt=1, model=None):
            seen.append(model.profile_id)
            return "boom" if model.profile_id == "p/bad" else None

    monkeypatch.setattr(mp, "resolve_model_profile", lambda ref, project_root=None: SimpleNamespace(profile_id=ref, parameters={}))
    d = D()
    assert d.preflight(wf_root, models=["p/a", "p/default", "p/a", ""]) is None
    assert seen == ["p/default", "p/a"]
    seen.clear()
    assert d.preflight(wf_root, models=["p/bad"]) == "p/bad：boom"


def test_runner_passes_agent_models_to_preflight(monkeypatch, wf_root):
    from backend.workflow import agent_models

    client, svc = _client(monkeypatch, wf_root)
    agent_models.save(wf_root, "a", "reviewer", model="p/rev")
    got = {}

    class F(FakeDriver):
        def preflight(self, ws, models=None):
            got["models"] = models
            return None

    svc.driver_factory = lambda r: F()
    assert client.post("/api/workflow/start", json={"workflow": "full-lca", "plan": "# 计划\n"}).status_code == 200
    svc.wait(10)
    assert got["models"] == ["p/rev"]


def test_progress_items_stream(monkeypatch, wf_root):
    """#1: /api/workflow/progress returns structured items from the event log, paged by seq."""
    from backend.workflow.events import EventLog

    client, svc = _client(monkeypatch, wf_root)
    assert client.post("/api/workflow/start", json={"workflow": "full-lca", "plan": "# 计划\n"}).status_code == 200
    svc.wait(10)
    ws = wf_root / "workspace"
    before = sorted(str(p) for p in wf_root.rglob("*"))
    p = client.get("/api/workflow/progress").json()
    assert p["status"] == "completed" and p["reset"] is True and p["workflow"] == "full-lca"
    assert p["items"] and all(i["seq"] <= p["next_seq"] for i in p["items"])
    assert any(i["kind"] == "note" and "开始运行 full-lca" in i["text"] for i in p["items"])
    again = client.get("/api/workflow/progress", params={"after_seq": p["next_seq"], "run_id": p["run_id"]}).json()
    assert again["items"] == [] and again["reset"] is False
    assert sorted(str(x) for x in wf_root.rglob("*")) == before  # read-only
    ev = EventLog(ws, run_id=p["run_id"])
    ev.emit("node_start", node="a", rev=1, redo={"target": "a"})
    turn = ev.bind(node="a", rev=1, agent="executor", attempt=1)
    turn.emit("turn_start", model="p/m-1")
    turn.emit("assistant_text", summary="开始")
    turn.emit("tool_call", tool="read", tool_call_id="c1", summary=f"{wf_root}/workspace/x.md")
    turn.emit("tool_result", tool="read", tool_call_id="c1", is_error=True, summary="not found")
    turn.emit("tool_call", tool="mcp__submit__submit", tool_call_id="c2", summary="", handoff=True)
    new = client.get("/api/workflow/progress", params={"after_seq": p["next_seq"], "run_id": p["run_id"]}).json()
    kinds = [i["kind"] for i in new["items"]]
    assert kinds == ["note", "assistant_text", "tool_call", "tool_result", "tool_call"]
    assert new["items"][0]["text"] == "开始阶段 a（重做 1）" and new["items"][1]["model"] == "p/m-1"
    assert new["items"][2]["summary"] == "workspace/x.md" and new["items"][3]["is_error"] is True
    assert new["items"][4]["handoff"] is True and new["items"][1]["redo"] == 1
    other = client.get("/api/workflow/progress", params={"after_seq": 999, "run_id": "old"}).json()
    assert other["reset"] is True and other["items"][0]["seq"] == p["items"][0]["seq"]
    assert client.get("/api/workflow/activity").status_code == 404
    wl = client.get("/api/workflows").json()["workflows"]
    assert wl[0]["id"] == "full-lca" and wl[0]["mode"] == "main"
    assert sorted(str(p) for p in wf_root.rglob("*")) == before
