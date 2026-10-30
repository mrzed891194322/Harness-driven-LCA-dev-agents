"""Outer queue (WORKFLOW_DESIGN §1): a plain Python deque of (node, rev) items; each item runs its inner graph.

The only non-linearity is an approved ``redo_upstream``: the segment target..requester is inserted right
after the requester at rev = 1 + highest existing rev (decision Q1), counted against ``max_redos``.
``runs/_run/queue.json`` is written at every item boundary; resume restarts the first unfinished item
(its runs dir and its rev outputs are cleared first). Items never resume mid-node.
"""
from __future__ import annotations

import fcntl
import json
import logging
import shutil
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from backend.workflow import layout, revisions
from backend.workflow.checks import host_produce_errors, requires_errors
from backend.workflow.config import Node, Spec, Workflow, load_spec
from backend.workflow.events import EventLog
from backend.workflow.work_record import write_work_record
from backend.workflow.node_graph import NodeContext, NodeGraph, NodeOutcome
from backend.workflow.turn import AgentDriver, PromptBuilder, TurnRequest, TurnResult

log = logging.getLogger("harness.workflow")

__all__ = ["Runner", "RunFailed", "RunStopped", "QueueItem", "TurnRequest", "TurnResult"]

QUEUE_FILE = "queue.json"


@dataclass
class QueueItem:
    node: str
    rev: int = 0
    reason: dict | None = None  # redo: {requested_by, target, artifact, field, evidence, requested_change}

    @property
    def key(self) -> str:
        return self.node if not self.rev else f"{self.node}@rev{self.rev}"


class RunFailed(RuntimeError):
    pass


class RunStopped(RunFailed):
    """The user asked to stop; the run ends ``stopped`` (never ``completed``)."""


def _default_prompt(node: Node, agent: str, attempt: int, feedback: str | None, specs: dict[str, Spec],
                    context: dict | None = None) -> str:
    text = f"节点 {node.run_key}，agent {agent}，第 {attempt} 轮。"
    if feedback:
        tag = "re_review" if node.role(agent) == "reviewer" else "rework"
        text += f"\n<{tag}>\n{feedback}\n</{tag}>"
    return text


class Runner:
    def __init__(self, root: Path, workflow: Workflow, nodes: list[Node], driver: AgentDriver, *,
                 workspace: Path | None = None, prompt_builder: PromptBuilder | None = None,
                 stop_requested: Callable[[], bool] = lambda: False, retry_interval: float = 2.0) -> None:
        self.root = root
        self.workflow = workflow
        self.nodes = {n.id: n for n in nodes}
        self.order = [n.id for n in nodes]
        self.driver = driver
        self.ws = workspace or (root / layout.WORKSPACE)
        self.art = self.ws / "artifacts"
        self.run_dir = self.ws / "runs" / "_run"
        self.events = EventLog(self.ws)
        self.prompt_builder = prompt_builder or _default_prompt
        self.stop_requested = stop_requested
        self.retry_interval = retry_interval
        self.specs = {p.spec: load_spec(root, p.spec) for n in nodes for p in n.produces}
        self.run_id = ""
        self.queue: deque[QueueItem] = deque()
        self.done: list[dict[str, Any]] = []
        self.redos = 0

    # ---------- workspace ----------
    def prepare_fresh(self, plans: dict[str, str]) -> None:
        """Clear runs/ and tmp/ (keep the lock file); clear artifacts/ unless ``start_rev: next``; write plans."""
        keep_artifacts = self.workflow.start_rev == "next"
        if keep_artifacts:
            self._drop_unfinished_revs()
        for child in ("artifacts", "runs", "tmp"):
            target = self.ws / child
            if not target.exists() or (keep_artifacts and child == "artifacts"):
                continue
            for item in target.iterdir():
                if item.name == "README.md":  # tracked placeholder
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
        from backend.services.plan_form import stage_references_for_run

        staged = stage_references_for_run(self.root, self.ws)
        if staged["bom"] or staged["lci"]:
            self.events.emit("references_staged", **staged)

    def _drop_unfinished_revs(self) -> None:
        """A fresh ``start_rev: next`` run must not build on the previous run's unfinished revs (failed/stopped)."""
        path = self.run_dir / QUEUE_FILE
        if not path.is_file():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        items = [d for d in data.get("done") or [] if d.get("outcome") != "passed"] + list(data.get("queue") or [])
        for d in items:
            node = self.nodes.get(d.get("node", ""))
            if node is not None and int(d.get("rev") or 0) > 0:
                revisions.clear(self.art, node, int(d["rev"]))

    # ---------- state files ----------
    def _status_path(self, key: str) -> Path:
        return layout.node_dir(self.ws, key) / "status.json"

    def item_status(self, item: QueueItem) -> dict[str, Any]:
        path = self._status_path(item.key)
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"status": "pending"}

    def _set_item(self, item: QueueItem, status: str, **extra: Any) -> None:
        path = self._status_path(item.key)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"node": item.node, "rev": item.rev, "status": status, "updated_at": time.time(), **extra}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._manifest(current_node=item.node if status == "running" else None,
                       current_rev=item.rev if status == "running" else None)

    def _items(self) -> list[QueueItem]:
        return [QueueItem(d["node"], d["rev"]) for d in self.done] + list(self.queue)

    def _manifest(self, **fields: Any) -> None:
        path = self.run_dir / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        data.update({"engine": "workflow", "run_id": self.run_id, "workflow": self.workflow.id,
                     "nodes": [{"id": it.node, "rev": it.rev, "key": it.key, **self.item_status(it)}
                               for it in self._items()]})
        data.update(fields)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _save_queue(self) -> None:
        data = {"run_id": self.run_id, "workflow": self.workflow.id, "done": self.done,
                "queue": [asdict(it) for it in self.queue], "redos": self.redos}
        tmp = self.run_dir / (QUEUE_FILE + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.run_dir / QUEUE_FILE)

    def _initial_queue(self) -> deque[QueueItem]:
        nxt = self.workflow.start_rev == "next"
        return deque(QueueItem(n, revisions.next_rev(self.art, self.nodes[n]) if nxt else 0) for n in self.order)

    def _load_queue(self) -> bool:
        path = self.run_dir / QUEUE_FILE
        if not path.is_file():
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        self.done = list(data.get("done") or [])
        self.queue = deque(QueueItem(**it) for it in data.get("queue") or [])
        self.redos = int(data.get("redos") or 0)
        # status.json is the per-node truth: the first done item that is not completed
        # (edited, crashed mid-write) and everything after it go back into the queue.
        for i, d in enumerate(self.done):
            it = QueueItem(d["node"], d["rev"], d.get("reason", ""))
            if self.item_status(it).get("status") not in ("passed", "completed"):
                back = [QueueItem(x["node"], x["rev"], x.get("reason", "")) for x in self.done[i:]]
                self.done = self.done[:i]
                self.queue.extendleft(reversed(back))
                break
        return True

    # ---------- run ----------
    def run(self, *, plans: dict[str, str] | None = None, resume: bool = False) -> str:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.run_dir / "orchestrator.lock"
        with lock_path.open("a+") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RunFailed("已有运行持有 orchestrator.lock") from exc
            if resume:
                old = self.run_dir / "manifest.json"
                prev = json.loads(old.read_text(encoding="utf-8")) if old.is_file() else {}
                self.run_id = prev.get("run_id") or uuid.uuid4().hex
                if not self._load_queue():
                    self.queue = self._initial_queue()
            else:
                self.prepare_fresh(plans or {})
                self.run_id = uuid.uuid4().hex
                self.queue = self._initial_queue()
            self.events = EventLog(self.ws, run_id=self.run_id)
            self._save_queue()
            self.events.emit("lock_acquired", path=str(lock_path))
            self.events.emit("run_start", workflow=self.workflow.id, nodes=[it.key for it in self.queue],
                             resume=resume)
            self._manifest(status="running", status_reason="", started_at=time.time())
            err = self._preflight()
            if err:
                reason = f"模型鉴权预检失败：{err}"
                if self.queue:
                    self._set_item(self.queue[0], "failed", error=reason, reason="model_preflight")
                    self.events.emit("node_end", node=self.queue[0].node, rev=self.queue[0].rev, outcome="failed",
                                     reason="model_preflight", error=reason)
                return self._end("failed", reason)
            try:
                while self.queue:
                    item = self.queue[0]
                    out = self._run_item(item)
                    self.queue.popleft()
                    self.done.append({"node": item.node, "rev": item.rev, "outcome": out.kind})
                    if out.kind == "redo_upstream":
                        self._insert_redo(item, out)
                    self._save_queue()
                    if self.stop_requested():  # also after the last node: a stop is never swallowed
                        raise RunStopped(f"用户停止（{item.key} 已完成后）")
            except RunStopped as exc:
                return self._end("stopped", str(exc))
            except RunFailed as exc:
                self._save_queue()
                return self._end("failed", str(exc))
            except Exception as exc:  # host bug: never leave the run "running"
                log.exception("v5 run crashed")
                reason = f"host_error: {type(exc).__name__}: {exc}"[:500]
                if self.queue:
                    try:
                        self._set_item(self.queue[0], "failed", reason="host_error", error=reason)
                    except Exception:  # noqa: BLE001
                        log.exception("could not mark node failed")
                try:
                    self._save_queue()
                except Exception:  # noqa: BLE001
                    log.exception("could not save queue")
                return self._end("failed", reason)
            return self._end("completed", "全部节点已通过")

    def _end(self, status: str, reason: str) -> str:
        """Terminal state: the manifest is written even when the event log fails."""
        try:
            self.events.emit("run_end", status=status, reason=reason)
        except Exception:  # noqa: BLE001
            log.exception("run_end event failed")
        self._manifest(status=status, status_reason=reason, current_node=None, current_rev=None, ended_at=time.time())
        try:
            man_path = self.run_dir / "manifest.json"
            man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.is_file() else {}
            write_work_record(self.ws, manifest=man if isinstance(man, dict) else {})
        except Exception:  # noqa: BLE001
            log.exception("work-record write failed")
        return status

    def _preflight(self) -> str | None:
        pre = getattr(self.driver, "preflight", None)
        if not callable(pre):
            return None
        import inspect

        models = sorted({a.model for n in self.nodes.values() for a in n.agents.values() if a.model})
        return pre(self.ws, models=models) if "models" in inspect.signature(pre).parameters else pre(self.ws)

    # ---------- redo ----------
    def _redo_targets(self, item: QueueItem) -> dict[str, list[str]]:
        """Earlier nodes this item may ask to redo: {node: [produce rel paths]} (spec upstream.may_redo narrows)."""
        if self.workflow.max_redos == 0:
            return {}
        node = self.nodes[item.node]
        earlier = self.order[: self.order.index(item.node)]
        allowed: set[str] | None = None
        for prod in node.produces:
            may = self.specs[prod.spec].upstream.may_redo
            if may is not None:
                allowed = (allowed or set()) | set(may)
        return {n: [p.path for p in self.nodes[n].produces] for n in earlier
                if self.nodes[n].produces and (allowed is None or n in allowed)}

    def _insert_redo(self, item: QueueItem, out: NodeOutcome) -> None:
        redo = out.redo or {}
        target = str(redo.get("target_node") or "")
        if target not in self._redo_targets(item):
            self.events.emit("redo_refused", node=item.node, rev=item.rev, target=target, reason="redo_target_invalid")
            self._set_item(item, "failed", reason="redo_target_invalid", error=f"回溯目标非法：{target}")
            raise RunFailed(f"redo_target_invalid: {item.key} 请求重做 {target!r}")
        if self.redos >= self.workflow.max_redos:
            msg = f"redo_limit: 已达 max_redos={self.workflow.max_redos}，{item.node} 请求重做 {target} 被拒"
            self.events.emit("redo_refused", node=item.node, rev=item.rev, target=target, reason="max_redos")
            self._set_item(item, "failed", reason="redo_limit", error=msg)
            raise RunFailed(msg)
        self.redos += 1
        segment = self.order[self.order.index(target): self.order.index(item.node) + 1]
        reason = {"requested_by": item.key, "target": target,
                  **{k: redo.get(k) for k in ("artifact", "field", "evidence", "requested_change")}}
        new = [QueueItem(n, revisions.next_rev(self.art, self.nodes[n]), reason) for n in segment]
        self.queue.extendleft(reversed(new))
        self.events.emit("queue_append", items=[{"node": i.node, "rev": i.rev} for i in new],
                         requested_by=item.key, target=target, redos=self.redos)
        self._manifest()

    # ---------- one item ----------
    def _run_item(self, item: QueueItem) -> NodeOutcome:
        base = self.nodes[item.node]
        ev = self.events.bind(node=item.node, rev=item.rev)
        prev = self.item_status(item)
        if prev.get("status") != "pending":
            ev.emit("node_clear", previous=prev.get("status"))
        shutil.rmtree(layout.node_dir(self.ws, item.key), ignore_errors=True)
        revisions.clear(self.art, base, item.rev)
        node = revisions.at_rev(self.art, base, item.rev)
        errors = requires_errors(self.art, node)
        if errors:
            ev.emit("requires_failed", errors=errors)
            self._set_item(item, "error", error="; ".join(errors))
            raise RunFailed(f"{item.key} 前置产物不可用：" + "; ".join(errors))
        ev.emit("node_start", title=node.title, requires_resolved=node.requires,
                produces=[p.path for p in node.produces], redo=item.reason)
        self._set_item(item, "running", round=1)
        ctx = NodeContext(workspace=self.ws, run_id=self.run_id, driver=self.driver,
                          prompt_builder=self.prompt_builder, specs=self.specs, events=ev,
                          host_checks=lambda n: host_produce_errors(self.art, n, self.specs),
                          stop_requested=self.stop_requested, redo_targets=self._redo_targets(item),
                          redo=item.reason, retry_interval=self.retry_interval)
        out = NodeGraph(node, ctx).run()
        rounds = out.attempts.get(node.flow.start, 0)
        ev.emit("node_end", outcome=out.kind, reason=out.code, detail=out.reason, steps=out.steps, attempts=out.attempts)
        if out.kind == "passed":
            self._set_item(item, "passed", round=rounds)
        elif out.kind == "redo_upstream":
            self._set_item(item, "redo_upstream", round=rounds, redo=out.redo)
        elif out.kind == "stopped":
            self._set_item(item, "stopped", round=rounds)
            raise RunStopped(out.reason)
        else:
            status = "error" if out.fatal else out.kind  # failed | blocked
            self._set_item(item, status, round=rounds, error=out.reason, reason=out.code)
            raise RunFailed(f"{item.key} {'阻塞' if out.kind == 'blocked' else '失败'}：{out.reason}")
        return out
