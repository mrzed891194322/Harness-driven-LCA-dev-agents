"""v5 run control for the API: start / stop / resume / status, one run at a time in a thread."""
from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from backend.v5 import layout
from backend.v5.config import list_workflows, load_workflow
from backend.v5.events import EventLog
from backend.v5.inject import Injector
from backend.v5.runner import AgentDriver, Runner

DriverFactory = Callable[[Path], AgentDriver]


def _default_driver(root: Path) -> AgentDriver:
    from backend.core.agents.assignment_models import load_default_model
    from backend.core.runtime.model_profiles import resolve_model_profile
    from backend.v5.pi_driver import PiDriver

    ref = load_default_model(root)
    if not ref:
        raise ValueError("尚未选择模型：请先在模型页选择默认模型")
    return PiDriver(root, resolve_model_profile(ref, project_root=root))


class V5Service:
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
        out = []
        for wid in list_workflows(self.root):
            wf, nodes = load_workflow(self.root, wid)
            out.append({"id": wid, "title": wf.title, "plan_file": wf.plan_file, "revise_of": wf.revise_of,
                        "nodes": [n.id for n in nodes],
                        "details": [self._node_card(n) for n in nodes]})
        return out

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
        """Read-only GUI card: spec at node level; per agent model+thinking / role / access / tools / rules."""
        from backend.v5.access import compute_scope
        from backend.v5.config import load_role

        from backend.v5 import agent_models

        agents = {}
        default_ref, default_thinking = self._default_model()
        overrides = agent_models.load(self.root)
        for name, yaml_agent in node.agents.items():
            gui = overrides.get(f"{node.id}.{name}", {})
            agent = agent_models.apply([node], overrides)[0].agents[name]
            scope = compute_scope(self.root, node, name, load_role(self.root, agent.role)[1])
            rel = lambda g: g.replace(str(self.root) + "/", "")  # noqa: E731
            agents[name] = {"role": agent.role, "model": agent.model or default_ref or "未选择模型",
                            "model_source": "gui" if gui.get("model") else "agent" if yaml_agent.model else "default",
                            "gui_model": gui.get("model", ""), "gui_thinking": gui.get("thinking", ""),
                            "thinking": agent.thinking or default_thinking or "模型默认",
                            "tools": {"mcp": agent.tools.mcp, "skills": agent.tools.skills},
                            "rules": list(node.inject) + list(agent.rules),
                            "read": [rel(g) for g in scope.read_globs], "write": [rel(g) for g in scope.write_globs]}
        return {"id": node.id, "title": node.title, "requires": node.requires,
                "produces": [{"spec": p.spec, "path": p.path} for p in node.produces],
                "max_rounds": node.flow.max_rounds, "agents": agents}

    def preview(self, workflow: str) -> dict[str, Any]:
        """Exact injection per agent (system + round-1 user message) via the run-time Injector. Read-only."""
        from backend.v5 import agent_models
        from backend.v5.config import load_spec

        wf, nodes = load_workflow(self.root, workflow)
        nodes = agent_models.apply(nodes, agent_models.load(self.root))
        specs = {p.spec: load_spec(self.root, p.spec) for n in nodes for p in n.produces}
        inj = Injector(self.root, self.ws)
        plan_dir = self.ws / "artifacts" / "plan"
        out = []
        for node in nodes:
            agents = []
            for role in node.agents:
                agents.append({"role": role, "system": inj.system(node, role), "user": inj(node, role, 1, None, specs)})
            out.append({"id": node.id, "title": node.title, "agents": agents})
        return {"workflow": wf.id if hasattr(wf, "id") else workflow, "plan_file": wf.plan_file,
                "plan_present": plan_dir.is_dir() and any(plan_dir.glob("*.md")), "nodes": out}

    def start(self, workflow: str, *, plan_text: str = "", resume: bool = False,
              extra_plans: dict[str, str] | None = None) -> dict[str, Any]:
        wf, nodes = load_workflow(self.root, workflow)  # ConfigError -> 400 at API
        from backend.v5 import agent_models

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
                    EventLog(self.ws).emit("run_end", status="failed", reason=str(exc))
                finally:
                    release = getattr(driver, "release_all", None)
                    if release:
                        release()

            self._thread = threading.Thread(target=work, name="v5-run", daemon=True)
            self._thread.start()
        return {"status": "started", "workflow": workflow, "resume": resume}

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
            nid = item["id"] if isinstance(item, dict) else str(item)
            st = _read_json(layout.node_dir(self.ws, nid) / "status.json")
            fb = layout.node_dir(self.ws, nid) / "feedback"
            nodes.append({"id": nid, "status": st.get("status", "pending"), "round": st.get("round", 0),
                          "error": st.get("error", ""),
                          "feedback_rounds": sorted(int(p.stem.split("_")[1]) for p in fb.glob("round_*.md"))
                          if fb.is_dir() else []})
        status = manifest.get("status") or "idle"
        if self.running and status not in ("running",):
            status = "running"
        return {"status": status, "reason": manifest.get("status_reason") or self.last_error,
                "run_id": manifest.get("run_id", ""), "workflow": manifest.get("workflow", ""),
                "current_node": manifest.get("current_node"), "nodes": nodes, "running": self.running}

    def feedback(self, node: str, rnd: int) -> str:
        if not node.replace("-", "").replace("_", "").isalnum():
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

