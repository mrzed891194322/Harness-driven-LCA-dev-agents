"""workflow run control for the API: start / stop / resume / status, one run at a time in a thread."""
from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from backend.workflow import layout
from backend.workflow.config import back_edge_rounds, list_workflows, load_workflow
from backend.workflow.events import EventLog
from backend.workflow.inject import Injector
from backend.workflow.runner import Runner
from backend.workflow.turn import AgentDriver

log = logging.getLogger("harness.workflow")

DriverFactory = Callable[[Path], AgentDriver]


def _default_driver(root: Path) -> AgentDriver:
    from backend.core.agents.assignment_models import load_default_model
    from backend.core.runtime.model_profiles import resolve_model_profile
    from backend.workflow.pi_driver import PiDriver

    ref = load_default_model(root)
    if not ref:
        raise ValueError("尚未选择模型：请先在模型页选择默认模型")
    return PiDriver(root, resolve_model_profile(ref, project_root=root))


class WorkflowService:
    def __init__(self, root: Path, *, workspace: Path | None = None,
                 driver_factory: DriverFactory = _default_driver) -> None:
        self.root = root
        self.ws = workspace or (root / layout.WORKSPACE)
        self.driver_factory = driver_factory
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._driver: Any = None
        self.last_error = ""

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def workflows(self) -> list[dict[str, Any]]:
        global_rules = self._global_rule_cards()
        out = []
        for wid in list_workflows(self.root):
            wf, nodes = load_workflow(self.root, wid)
            out.append({"id": wid, "title": wf.title, "plan_file": wf.plan_file, "start_rev": wf.start_rev, "max_redos": wf.max_redos,
                        "nodes": [n.id for n in nodes],
                        "global_rules": global_rules,
                        "details": [self._node_card(n) for n in nodes]})
        return out

    def _global_rule_cards(self) -> list[dict[str, Any]]:
        """Harness global rules (inject step 1), same files for all workflows."""
        from backend.workflow import layout
        from backend.workflow.config import load_rule

        folder = self.root / layout.RULES_GLOBAL
        if not folder.is_dir():
            return []
        cards = []
        for path in sorted(folder.glob("*.yaml")):
            rel = str(path.relative_to(self.root / "harness"))
            try:
                rule = load_rule(self.root, rel)
            except Exception:  # noqa: BLE001 — card must still render
                cards.append({"id": rel, "title": path.stem, "path": rel, "enabled": True, "applies_to": None})
                continue
            if not rule.enabled:
                continue
            cards.append({"id": rule.id or rel, "title": rule.title, "path": rel,
                          "enabled": rule.enabled, "applies_to": rule.applies_to})
        return cards

    def _default_model(self) -> tuple[str, str]:
        """(model ref, thinking) the driver would use when an agent sets neither (I-37)."""
        try:
            from backend.core.agents.assignment_models import load_default_model
            from backend.core.runtime.model_profiles import resolve_model_profile

            ref = load_default_model(self.root)
            if not ref:
                return "", ""
            prof = resolve_model_profile(ref, project_root=self.root)
            return ref, str((prof.parameters or {}).get("thinking") or "")
        except Exception:  # noqa: BLE001 - a card must render even with a broken model store
            return "", ""

    def _node_card(self, node: Any) -> dict[str, Any]:
        """Read-only GUI card: spec at node level; per agent model+thinking / template / access / tools / rules."""
        from backend.workflow.access import compute_scope
        from backend.workflow import agent_models

        agents = {}
        default_ref, default_thinking = self._default_model()
        overrides = agent_models.load(self.root)
        for name, yaml_agent in node.agents.items():
            gui = overrides.get(f"{node.id}.{name}", {})
            agent = agent_models.apply([node], overrides)[0].agents[name]
            scope = compute_scope(self.root, node, name, agent.definition.access)
            rel = lambda g: g.replace(str(self.root) + "/", "")  # noqa: E731
            agents[name] = {"template": agent.agent, "model": agent.model or default_ref or "未选择模型",
                            "model_source": "gui" if gui.get("model") else "agent" if yaml_agent.model else "default",
                            "gui_model": gui.get("model", ""), "gui_thinking": gui.get("thinking", ""),
                            "thinking": agent.thinking or default_thinking or "模型默认",
                            "submit": node.kind(name),  # artifact = 主 agent (§8); verdict = reviewer
                            "tools": {"mcp": agent.tools.mcp, "skills": agent.tools.skills},
                            # agent-level only (inject step: node.inject + agent.rules); node.inject is on the node card
                            "rules": list(agent.rules),
                            "read": [rel(g) for g in scope.read_globs], "write": [rel(g) for g in scope.write_globs]}
        flow = {
            "start": node.flow.start,
            "edges": [{"from": e.from_, "when": e.when, "to": e.to,
                       **({"max": e.max} if e.max is not None else {})}
                      for e in node.flow.edges],
        }
        return {"id": node.id, "title": node.title, "requires": node.requires,
                "produces": [{"spec": p.spec, "path": p.path} for p in node.produces],
                "inject": list(node.inject),
                "max_rounds": back_edge_rounds(node), "flow": flow, "agents": agents}

    def preview(self, workflow: str, plan_text: str | None = None) -> dict[str, Any]:
        """Exact injection per agent (system + round-1 user message) via the run-time Injector. Read-only."""
        from backend.workflow import agent_models
        from backend.workflow.config import load_spec

        wf, nodes = load_workflow(self.root, workflow)
        nodes = agent_models.apply(nodes, agent_models.load(self.root))
        specs = {p.spec: load_spec(self.root, p.spec) for n in nodes for p in n.produces}
        inj = Injector(self.root, self.ws)
        if plan_text and plan_text.strip():
            inj.plan_override = {wf.plan_file: plan_text}
        plan_dir = self.ws / "artifacts" / "plan"
        out = []
        for node in nodes:
            agents = []
            for key in node.agents:
                agents.append({"agent": key, "system": inj.system(node, key), "user": inj(node, key, 1, None, specs)})
            out.append({"id": node.id, "title": node.title, "agents": agents})
        return {"workflow": wf.id if hasattr(wf, "id") else workflow, "plan_file": wf.plan_file,
                "plan_present": bool(plan_text and plan_text.strip()) or (plan_dir.is_dir() and any(plan_dir.glob("*.md"))),
                "plan_source": "saved" if plan_text and plan_text.strip() else "workspace", "nodes": out}

    def start(self, workflow: str, *, plan_text: str = "", resume: bool = False,
              extra_plans: dict[str, str] | None = None) -> dict[str, Any]:
        wf, nodes = load_workflow(self.root, workflow)  # ConfigError -> 400 at API
        from backend.workflow import agent_models

        nodes = agent_models.apply(nodes, agent_models.load(self.root))  # /plan per-agent model, fixed at run start
        if not resume and not plan_text.strip():
            raise ValueError("计划为空：请先填写计划表单或导入计划")
        with self._lock:
            if self.running:
                raise RuntimeError("已有运行在进行中")
            driver = self.driver_factory(self.root)
            self._driver = driver
            self._stop.clear()
            self.last_error = ""
            plans = {wf.plan_file: plan_text, **(extra_plans or {})} if not resume else None
            runner = Runner(self.root, wf, nodes, driver, workspace=self.ws,
                            prompt_builder=Injector(self.root, self.ws), stop_requested=self._stop.is_set)

            def work() -> None:
                try:
                    runner.run(plans=plans, resume=resume)
                except Exception as exc:  # noqa: BLE001
                    self.last_error = str(exc)
                    self._fail_run(f"host_error: {type(exc).__name__}: {exc}"[:500])
                finally:
                    release = getattr(driver, "release_all", None)
                    if release:
                        release()

            self._thread = threading.Thread(target=work, name="workflow-run", daemon=True)
            self._thread.start()
        return {"status": "started", "workflow": workflow, "resume": resume}

    def _fail_run(self, reason: str) -> None:
        """Uncaught error in the run thread: run_end (best effort) + manifest failed. The flock on
        orchestrator.lock is released when Runner.run's ``with`` closes the file."""
        try:
            EventLog(self.ws).emit("run_end", status="failed", reason=reason)
        except Exception:  # noqa: BLE001
            log.exception("run_end event failed")
        path = self.ws / "runs" / "_run" / "manifest.json"
        data = _read_json(path)
        if data.get("status") in (None, "running"):
            data.update(status="failed", status_reason=reason, current_node=None, current_rev=None,
                        ended_at=time.time())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def stop(self) -> dict[str, str]:
        if not self.running:
            raise RuntimeError("当前没有运行")
        self._stop.set()
        EventLog(self.ws).emit("stop_requested")
        cancel = getattr(self._driver, "cancel", None)
        if callable(cancel):
            try:
                cancel()  # abort the active agent turn (same path as a turn abort)
            except Exception as exc:  # noqa: BLE001
                EventLog(self.ws).emit("stop_cancel_failed", error=str(exc)[:300])
        return {"status": "stopping"}

    def wait(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def status(self) -> dict[str, Any]:
        run_dir = self.ws / "runs" / "_run"
        manifest = _read_json(run_dir / "manifest.json")
        nodes = []
        for item in manifest.get("nodes") or []:
            nid, rev = item["id"], int(item.get("rev") or 0)
            key = item.get("key") or nid
            st = _read_json(layout.node_dir(self.ws, key) / "status.json")
            fb = layout.node_dir(self.ws, key) / "feedback"
            nodes.append({"id": nid, "rev": rev, "key": key, "status": st.get("status", "pending"),
                          "round": st.get("round", 0),
                          "error": st.get("error", ""),
                          "feedback_rounds": sorted(int(p.stem.split("_")[1]) for p in fb.glob("round_*.md"))
                          if fb.is_dir() else []})
        status = manifest.get("status") or "idle"
        if self.running and status not in ("running",):
            status = "running"
        return {"status": status, "reason": manifest.get("status_reason") or self.last_error,
                "run_id": manifest.get("run_id", ""), "workflow": manifest.get("workflow", ""),
                "current_node": manifest.get("current_node"), "current_rev": manifest.get("current_rev"), "nodes": nodes, "running": self.running}

    def progress(self, after_seq: int = 0, run_id: str = "") -> dict[str, Any]:
        """#1 /api/workflow/progress: run status + structured activity items with ``seq`` > ``after_seq``.

        ``reset`` is true when the client's ``run_id`` is not the current run; items then start from seq 0."""
        from backend.workflow.activity import cached_progress

        st = self.status()
        status = {"stopped": "interrupted"}.get(st["status"], st["status"])
        cur = st.get("current_node") or ""
        reason = st.get("reason") or ""
        if status in ("failed", "interrupted"):
            errs = [f"{n.get('key') or n['id']}：{n['error']}" for n in st["nodes"] if n.get("error")]
            reason = "\n".join([r for r in [reason, *errs] if r])
        current = st.get("run_id") or ""
        reset = run_id != current
        after = 0 if reset else max(0, int(after_seq))
        events, all_items = cached_progress(self.ws)
        attempt = 0
        for e in events:
            if e.get("kind") == "turn_start" and e.get("node") == cur and e.get("rev") == st.get("current_rev"):
                attempt = int(e.get("attempt") or 0)
        return {"run_id": current or None, "status": status, "status_reason": reason, "current_node": cur or None,
                "rev": st.get("current_rev"), "attempt": attempt or None, "model": self._default_model()[0],
                "workflow": st.get("workflow") or None, "reset": reset,
                "items": [i for i in all_items if i["seq"] > after],
                "next_seq": max((int(e.get("seq") or 0) for e in events), default=after)}

    def feedback(self, node: str, rnd: int) -> str:
        if not node.replace("-", "").replace("_", "").replace("@", "").isalnum():
            raise ValueError("bad node id")
        path = layout.node_dir(self.ws, node) / "feedback" / f"round_{int(rnd)}.md"
        if not path.is_file():
            raise FileNotFoundError(str(path))
        return path.read_text(encoding="utf-8")

    def events(self, offset: int = 0) -> dict[str, Any]:
        rows = EventLog(self.ws).read()
        return {"events": rows[offset:], "offset": len(rows)}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

