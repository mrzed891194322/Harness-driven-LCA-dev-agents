"""Linear v5 executor with per-node resume.

For each node: requires preflight -> executor turn -> host checks -> reviewer turn -> verdict,
following the node's flow graph up to ``max_rounds``. Agents talk only through files in
``runs/<node>/`` and the produces dirs. A node that passed is skipped on resume; a node that
stopped midway gets its runs dir and produces dirs cleared and reruns whole.
"""
from __future__ import annotations

import fcntl
import json
import shutil
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from backend.v5 import layout
from backend.v5.access import produce_dir
from backend.v5.checks import produce_errors, requires_errors
from backend.v5.config import Node, Spec, Workflow, load_spec
from backend.v5.events import EventLog


@dataclass
class TurnResult:
    submit: dict[str, Any] | None = None  # arguments of the fixed submit tool
    aborted: bool = False
    error: str = ""
    fatal: bool = False  # e.g. model auth failure: stop the whole run
    session_id: str = ""
    nudges: int = 0
    abort_reason: str = ""  # "max_turns" | "timeout" | "too_many_rejections" | ""


@dataclass
class TurnRequest:
    node: Node
    role: str
    round: int
    prompt: str
    workspace: Path
    run_id: str
    session_key: str
    resume: bool  # continue the same session (executor after reject)
    extra: dict[str, Any] = field(default_factory=dict)


class AgentDriver(Protocol):
    def run_turn(self, request: TurnRequest) -> TurnResult: ...


PromptBuilder = Callable[[Node, str, int, str | None, dict[str, Spec]], str]


class RunFailed(RuntimeError):
    pass


class RunStopped(RunFailed):
    """The user asked to stop; the run ends ``stopped`` (never ``completed``)."""


def _default_prompt(node: Node, role: str, rnd: int, rework: str | None, specs: dict[str, Spec]) -> str:
    text = f"节点 {node.id}，角色 {role}，第 {rnd} 轮。"
    if rework:
        text += f"\n<rework>\n{rework}\n</rework>"
    return text


class Runner:
    def __init__(
        self,
        root: Path,
        workflow: Workflow,
        nodes: list[Node],
        driver: AgentDriver,
        *,
        workspace: Path | None = None,
        prompt_builder: PromptBuilder | None = None,
        stop_requested: Callable[[], bool] = lambda: False,
    ) -> None:
        self.root = root
        self.workflow = workflow
        self.nodes = nodes
        self.driver = driver
        self.ws = workspace or (root / layout.WORKSPACE)
        self.art = self.ws / "artifacts"
        self.run_dir = self.ws / "runs" / "_run"
        self.events = EventLog(self.ws)
        self.prompt_builder = prompt_builder or _default_prompt
        self.stop_requested = stop_requested
        self.specs = {p.spec: load_spec(root, p.spec) for n in nodes for p in n.produces}
        self.run_id = ""

    # ---------- workspace ----------
    def _snapshot_previous(self) -> None:
        """Revise mode: move the earlier run's artifacts to artifacts/previous/ (plan stays in place).

        The base is replaced only after a completed run (full-lca or a completed revise). After a failed or
        stopped revise, the existing previous/ is the base again and the half-revised artifacts are dropped.
        """
        prev_dir = self.art / "previous"
        manifest = self.run_dir / "manifest.json"
        last = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
        keep_base = prev_dir.is_dir() and not (last.get("status") == "completed")
        if not keep_base:
            shutil.rmtree(prev_dir, ignore_errors=True)
            if self.art.is_dir():
                movable = [i for i in self.art.iterdir() if i.name not in ("plan", "previous", "README.md")]
                if movable:
                    prev_dir.mkdir(parents=True, exist_ok=True)
                    for item in movable:
                        shutil.move(str(item), str(prev_dir / item.name))
        self.events.emit("previous_snapshot", kept_existing=keep_base, base_workflow=last.get("workflow"),
                         base_status=last.get("status"), base_run=last.get("run_id"))

    def prepare_fresh(self, plans: dict[str, str]) -> None:
        """Clear the workspace (keep the lock file), then write the plan files.

        Revise workflows keep artifacts/plan/ and artifacts/previous/ (see ``_snapshot_previous``).
        """
        revise = bool(self.workflow.revise_of)
        if revise:
            self._snapshot_previous()
        for child in ("artifacts", "runs", "tmp"):
            target = self.ws / child
            if not target.exists():
                continue
            for item in target.iterdir():
                if item.name == "README.md":  # tracked placeholder
                    continue
                if revise and child == "artifacts" and item.name in ("plan", "previous"):
                    continue
                if item == self.run_dir:
                    for sub in item.iterdir():
                        if sub.name != "orchestrator.lock":
                            shutil.rmtree(sub) if sub.is_dir() else sub.unlink()
                    continue
                shutil.rmtree(item) if item.is_dir() and not item.is_symlink() else item.unlink()
        plan_dir = self.art / "plan"
        plan_dir.mkdir(parents=True, exist_ok=True)
        for name, text in plans.items():
            (plan_dir / name).write_text(text, encoding="utf-8")
        self.events.emit("plan_written", files=sorted(plans), bytes={k: len(v.encode()) for k, v in plans.items()})

    def _clear_node(self, node: Node) -> None:
        shutil.rmtree(layout.node_dir(self.ws, node.id), ignore_errors=True)
        for prod in node.produces:
            shutil.rmtree(self.art / produce_dir(prod.path), ignore_errors=True)

    # ---------- state ----------
    def _status_path(self, node: Node) -> Path:
        return layout.node_dir(self.ws, node.id) / "status.json"

    def node_status(self, node: Node) -> dict[str, Any]:
        path = self._status_path(node)
        if not path.is_file():
            return {"status": "pending"}
        return json.loads(path.read_text(encoding="utf-8"))

    def _set_node(self, node: Node, status: str, **extra: Any) -> None:
        path = self._status_path(node)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"node": node.id, "status": status, "updated_at": time.time(), **extra}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._manifest(current_node=node.id if status == "running" else None)

    def _manifest(self, **fields: Any) -> None:
        path = self.run_dir / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        data.update(
            {
                "engine": "v5",
                "run_id": self.run_id,
                "workflow": self.workflow.id,
                "nodes": [{"id": n.id, **self.node_status(n)} for n in self.nodes],
            }
        )
        data.update(fields)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- run ----------
    def run(self, *, plans: dict[str, str] | None = None, resume: bool = False) -> str:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.run_dir / "orchestrator.lock"
        with lock_path.open("a+") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RunFailed("已有运行持有 orchestrator.lock") from exc
            if not resume:
                self.prepare_fresh(plans or {})
                self.run_id = uuid.uuid4().hex
            else:
                old = self.run_dir / "manifest.json"
                prev = json.loads(old.read_text(encoding="utf-8")) if old.is_file() else {}
                self.run_id = prev.get("run_id") or uuid.uuid4().hex
            self.events.emit("lock_acquired", path=str(lock_path))
            self.events.emit("run_start", run_id=self.run_id, workflow=self.workflow.id,
                             nodes=[n.id for n in self.nodes], resume=resume)
            self._manifest(status="running", status_reason="", started_at=time.time())
            pre = getattr(self.driver, "preflight", None)
            err = pre(self.ws) if callable(pre) else None
            if err:
                reason = f"模型鉴权预检失败：{err}"
                first = next((n for n in self.nodes if not (resume and self.node_status(n).get("status") == "passed")),
                             None)
                if first is not None:
                    self._set_node(first, "failed", round=0, error=reason, reason="model_preflight")
                    self.events.emit("node_end", node=first.id, status="failed", reason="model_preflight",
                                     error=reason)
                self.events.emit("run_end", status="failed", reason=reason)
                self._manifest(status="failed", status_reason=reason, current_node=None, ended_at=time.time())
                return "failed"
            try:
                for node in self.nodes:
                    self._run_node(node, resume=resume)
                    if self.stop_requested():
                        raise RunStopped(f"用户停止（{node.id} 已完成后）")
            except RunStopped as exc:
                self.events.emit("run_end", status="stopped", reason=str(exc))
                self._manifest(status="stopped", status_reason=str(exc), current_node=None, ended_at=time.time())
                return "stopped"
            except RunFailed as exc:
                self.events.emit("run_end", status="failed", reason=str(exc))
                self._manifest(status="failed", status_reason=str(exc), current_node=None, ended_at=time.time())
                return "failed"
            self.events.emit("run_end", status="completed")
            self._manifest(status="completed", status_reason="全部节点已通过", current_node=None, ended_at=time.time())
            return "completed"

    def _feedback(self, node: Node, rnd: int, text: str, source: str) -> Path:
        path = layout.node_dir(self.ws, node.id) / "feedback" / f"round_{rnd}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"<!-- source: {source} -->\n{text}\n", encoding="utf-8")
        self.events.emit("feedback_written", node=node.id, round=rnd, source=source, path=str(path))
        return path

    def _run_node(self, node: Node, *, resume: bool) -> None:
        prev = self.node_status(node)
        if resume and prev.get("status") == "passed":
            self.events.emit("node_skip", node=node.id, reason="already passed")
            return
        if prev.get("status") != "pending" or not resume:
            if prev.get("status") != "pending":
                self.events.emit("node_clear", node=node.id, previous=prev.get("status"))
            self._clear_node(node)
        errors = requires_errors(self.art, node)
        if errors:
            self.events.emit("requires_failed", node=node.id, errors=errors)
            self._set_node(node, "error", error="; ".join(errors))
            raise RunFailed(f"{node.id} 前置产物不可用：" + "; ".join(errors))
        self.events.emit("node_start", node=node.id)
        self._set_node(node, "running", round=1)

        state, rnd, rework = node.flow.start, 1, None
        sessions_started: set[str] = set()
        while state not in ("done", "failed"):
            if self.stop_requested():
                self._set_node(node, "stopped", round=rnd)
                self.events.emit("node_end", node=node.id, status="stopped", round=rnd)
                raise RunStopped(f"{node.id} 被用户停止")
            if rnd > node.flow.max_rounds:
                self._set_node(node, "failed", round=rnd - 1, error="超过最大轮数")
                self.events.emit("node_end", node=node.id, status="failed", reason="max_rounds")
                raise RunFailed(f"{node.id} 超过最大轮数 {node.flow.max_rounds}")
            role = state
            prompt = self.prompt_builder(node, role, rnd, rework, self.specs)
            key = f"{node.id}.{role}"
            req = TurnRequest(node=node, role=role, round=rnd, prompt=prompt, workspace=self.ws,
                              run_id=self.run_id, session_key=key,
                              resume=(role == "executor" and key in sessions_started))
            system_fn = getattr(self.prompt_builder, "system", None)
            if system_fn is not None:
                req.extra["system"] = system_fn(node, role)
            self.events.emit("turn_start", node=node.id, role=role, round=rnd, resume=req.resume)
            result = self.driver.run_turn(req)
            sessions_started.add(key)
            self.events.emit("agent_settled", node=node.id, role=role, round=rnd, aborted=result.aborted,
                             error=result.error, submitted=result.submit is not None,
                             session_id=result.session_id, nudges=result.nudges,
                             abort_reason=result.abort_reason)
            if result.submit is None and self.stop_requested():
                # The stop aborted this turn: the node is resumable, not failed.
                self._set_node(node, "stopped", round=rnd)
                self.events.emit("node_end", node=node.id, status="stopped", role=role, round=rnd)
                raise RunStopped(f"{node.id} 被用户停止（{role} 第 {rnd} 轮中断）")
            if result.fatal:
                self._set_node(node, "error", round=rnd, error=result.error)
                raise RunFailed(f"{node.id} 致命错误：{result.error}")
            if result.submit is None:
                # Only an accepted submit completes an agent turn.
                reason = result.abort_reason or ("aborted" if result.aborted else "no_submit")
                detail = f"{role} 未成功提交（{reason}）" + (f"：{result.error}" if result.error else "")
                self._set_node(node, "failed", round=rnd, error=detail, reason=reason)
                self.events.emit("node_end", node=node.id, status="failed", reason=reason, role=role, round=rnd)
                raise RunFailed(f"{node.id} {detail}")
            outcome = self._outcome(node, role, rnd, result)
            nxt = node.transition(state, outcome)
            self.events.emit("transition", node=node.id, frm=state, on=outcome, to=nxt, round=rnd)
            if nxt is None:
                self._set_node(node, "failed", round=rnd, error=f"{state} 没有 {outcome} 的出边")
                raise RunFailed(f"{node.id}: {state} 结果 {outcome} 无对应流转")
            if outcome in ("reject", "checks_failed"):
                rnd += 1
                rework = (layout.node_dir(self.ws, node.id) / "feedback" / f"round_{rnd - 1}.md").read_text(encoding="utf-8")
                self._set_node(node, "running", round=rnd)
            state = nxt
        if state == "failed":
            self._set_node(node, "failed", round=rnd, error="审核者或执行者给出 stop")
            self.events.emit("node_end", node=node.id, status="failed")
            raise RunFailed(f"{node.id} 已停止")
        self._set_node(node, "passed", round=rnd)
        self.events.emit("node_end", node=node.id, status="passed", rounds=rnd)

    def _outcome(self, node: Node, role: str, rnd: int, result: TurnResult) -> str:
        sub = result.submit
        if sub is None:
            return "error"
        if role == "executor":
            if sub.get("status") == "stop":
                return "stop"
            errors = produce_errors(self.art, node, self.specs)
            self.events.emit("checks", node=node.id, round=rnd, ok=not errors, errors=errors[:50])
            if errors:
                self._feedback(node, rnd, "宿主检查未通过，只改这些问题，其他保持不变：\n" +
                               "\n".join(f"- {e}" for e in errors), "host_checks")
                return "checks_failed"
            return "submitted"
        verdict = sub.get("verdict")
        self.events.emit("review_verdict", node=node.id, round=rnd, verdict=verdict)
        if verdict not in ("pass", "reject", "stop"):
            return "error"
        if verdict == "reject":
            self._feedback(node, rnd, "审核者送回，只改这些问题，其他保持不变：\n" + str(sub.get("feedback") or ""), "reviewer")
        return verdict
