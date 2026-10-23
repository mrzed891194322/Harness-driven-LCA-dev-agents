"""Inner graph (WORKFLOW_DESIGN §2): one LangGraph StateGraph per queue item, built from the node's agents + flow.

Each graph node = one agent turn: build prompt -> driver.run_turn -> host re-validates the submit -> route.
Routing reads only the structured submit (status / verdict). Back edges count against ``max``; all turns
against ``flow.max_steps``. Transport/model errors without a submit are retried once (RetryPolicy).
No checkpointer: a stopped or crashed node reruns whole (node-level resume in the outer queue).
"""
from __future__ import annotations

import operator
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.types import RetryPolicy

from backend.workflow import layout
from backend.workflow.config import SUBMIT_FIELD, TERMINALS, Node, Spec
from backend.workflow.events import EventLog
from backend.workflow.turn import AgentDriver, PromptBuilder, TurnRequest

from harness.tools.mcp.submit.schemas import validate as validate_submit


class TransientTurnError(RuntimeError):
    """Turn ended with a transport/model error and no submit: retried by RetryPolicy."""


class NodeStopped(RuntimeError):
    pass


class NodeFatal(RuntimeError):
    pass


class NodeState(TypedDict, total=False):
    node: str
    rev: int
    step: int
    attempts: dict[str, int]
    last: dict[str, dict]
    history: Annotated[list[dict], operator.add]
    feedback: str | None
    edges: dict[str, int]  # back-edge use counts, "from|when"
    checks: int  # host-check failures so far
    next: str
    outcome: dict | None


@dataclass
class NodeOutcome:
    kind: str  # passed | failed | blocked | redo_upstream | stopped
    reason: str = ""
    redo: dict | None = None
    steps: int = 0
    attempts: dict[str, int] = field(default_factory=dict)
    fatal: bool = False
    code: str = ""  # short reason code for status.json (no_submit subtype, back_edge_limit, ...)


@dataclass
class NodeContext:
    workspace: Path
    run_id: str
    driver: AgentDriver
    prompt_builder: PromptBuilder
    specs: dict[str, Spec]
    events: EventLog  # bound to node / rev
    host_checks: Callable[[Node], list[str]]
    stop_requested: Callable[[], bool] = lambda: False
    redo_targets: dict[str, list[str]] = field(default_factory=dict)  # {earlier node: [produce rel paths]}
    redo: dict | None = None  # why this queue item exists (redo segment)
    retry_interval: float = 2.0


def _issues_text(issues: list[dict]) -> str:
    return "\n".join(f"- 位置：{i.get('where', '')}；问题：{i.get('problem', '')}；应为：{i.get('expected', '')}"
                     for i in issues)


def _submit_event(sub: dict) -> dict:
    keep = {k: sub[k] for k in ("status", "verdict", "target_node", "artifact", "field") if k in sub}
    for k in ("summary", "reason", "comment", "evidence", "requested_change"):
        if sub.get(k):
            keep[k] = str(sub[k])[:500]
    if "issues" in sub:
        keep["issues"] = len(sub["issues"])
    if "artifacts" in sub:
        keep["artifacts"] = sub["artifacts"][:20]
    return keep


class NodeGraph:
    def __init__(self, node: Node, ctx: NodeContext) -> None:
        self.node, self.ctx = node, ctx
        self.art = ctx.workspace / "artifacts"
        graph = StateGraph(NodeState)
        retry = RetryPolicy(max_attempts=2, initial_interval=ctx.retry_interval, jitter=False,
                            retry_on=TransientTurnError)
        agents = list(node.agents)
        for agent in agents:
            graph.add_node(agent, self._agent_fn(agent), retry_policy=retry)
            graph.add_conditional_edges(agent, self._route, {**{a: a for a in agents}, END: END})
        graph.set_entry_point(node.flow.start)
        self.graph = graph.compile()

    # ---------- routing ----------
    @staticmethod
    def _route(state: NodeState) -> str:
        return END if state.get("outcome") else state["next"]

    def _terminal(self, terminal: str, agent: str, sub: dict, reason: str, state: NodeState) -> dict:
        if terminal == "done":
            return {"kind": "passed", "reason": reason}
        if terminal == "blocked":
            return {"kind": "blocked", "reason": sub.get("reason") or reason}
        if terminal == "redo_upstream":
            redo = (state.get("last") or {}).get(self.node.flow.start) or {}
            executor_last = next((v for k, v in (state.get("last") or {}).items()
                                  if self.node.kind(k) == "artifact" and v.get("status") == "redo_upstream"), redo)
            return {"kind": "redo_upstream", "reason": reason, "redo": dict(executor_last)}
        if sub.get("status") == "redo_upstream" and self.node.kind(agent) == "artifact":
            reason = "redo_needs_reviewer"
        return {"kind": "failed", "reason": sub.get("reason") if sub.get("verdict") == "terminate" else reason}

    def _next(self, agent: str, sub: dict, state: NodeState, update: dict) -> None:
        kind = self.node.kind(agent)
        value = sub.get(SUBMIT_FIELD[kind])
        edge = next((e for e in self.node.outgoing(agent) if e.when in (value, None)), None)
        if edge is None:
            update["outcome"] = {"kind": "failed", "reason": f"no_edge: {agent} {value}"}
            return
        to, reason, count = edge.to, f"{agent}:{value}", None
        if edge.max is not None:
            counts = dict(state.get("edges") or {})
            key = f"{agent}|{edge.when}"
            count = counts.get(key, 0) + 1
            counts[key] = count
            update["edges"] = counts
            if count > edge.max:
                to, reason = self.node.flow.on_exhausted, "back_edge_limit"
        self.ctx.events.emit("route", agent=agent, attempt=update["attempts"][agent], step=update["step"],
                             frm=agent, when=value, to=to, back_edge_count=count, max=edge.max)
        if to in TERMINALS:
            update["outcome"] = self._terminal(to, agent, sub, reason, state)
        else:
            update["next"] = to

    # ---------- one agent turn ----------
    def _agent_fn(self, agent: str):
        node, ctx = self.node, self.ctx
        kind = node.kind(agent)

        def fn(state: NodeState) -> dict:
            if ctx.stop_requested():
                raise NodeStopped(f"{node.run_key} 被用户停止")
            attempts = dict(state.get("attempts") or {})
            step = int(state.get("step") or 0) + 1
            if step > node.flow.max_steps:
                ctx.events.emit("route", agent=agent, step=step, to="failed", reason="max_steps")
                return {"outcome": {"kind": "failed", "reason": f"max_steps: 超过 {node.flow.max_steps} 轮"}}
            attempt = attempts.get(agent, 0) + 1
            last = dict(state.get("last") or {})
            executor_last = next((v for k, v in last.items() if node.kind(k) == "artifact"), None)
            context = {"redo": ctx.redo, "executor_last": executor_last, "redo_targets": ctx.redo_targets}
            feedback = state.get("feedback") if kind == "artifact" else None
            prompt = ctx.prompt_builder(node, agent, attempt, feedback, ctx.specs, context)
            submit_context = {
                "kind": kind, "artifacts_root": str(self.art),
                "produces": [{"path": str(self.art / p.path), "schema": ctx.specs[p.spec].schema_}
                             for p in node.produces] if kind == "artifact" else [],
                "redo_targets": ctx.redo_targets, "executor_last": executor_last,
            }
            req = TurnRequest(node=node, agent=agent, attempt=attempt, prompt=prompt, workspace=ctx.workspace,
                              run_id=ctx.run_id, session_key=f"{node.run_key}.{agent}",
                              resume=kind == "artifact" and attempt > 1, step=step,
                              extra={"submit_context": submit_context})
            system_fn = getattr(ctx.prompt_builder, "system", None)
            if system_fn is not None:
                req.extra["system"] = system_fn(node, agent)
            ev = ctx.events.bind(agent=agent, attempt=attempt, step=step)
            ev.emit("turn_start", model=node.agents[agent].model, resume=req.resume)
            result = ctx.driver.run_turn(req)
            ev.emit("turn_end", submitted=result.submit is not None, abort_reason=result.abort_reason,
                    error=result.error[:500], aborted=result.aborted, nudges=result.nudges)
            if result.fatal:
                raise NodeFatal(f"{node.run_key} 致命错误：{result.error}")
            if result.submit is None:
                if ctx.stop_requested():
                    raise NodeStopped(f"{node.run_key} 被用户停止（{agent} 第 {attempt} 轮中断）")
                if result.error and not result.abort_reason and not result.aborted:
                    raise TransientTurnError(result.error)
                why = result.abort_reason or ("aborted" if result.aborted else "no_submit")
                detail = f"no_submit: {agent} 未成功提交（{why}）" + (f"：{result.error}" if result.error else "")
                return {"attempts": {**attempts, agent: attempt}, "step": step,
                        "outcome": {"kind": "failed", "reason": detail, "code": why}}
            sub = {k: v for k, v in result.submit.items() if k not in ("submitted_at", "agent")}
            attempts[agent] = attempt
            update: dict[str, Any] = {"attempts": attempts, "step": step, "last": {**last, agent: sub},
                                      "history": [{"agent": agent, "attempt": attempt, **sub}]}
            errors = validate_submit(kind, sub, submit_context, check_files=False)
            if errors:
                ev.emit("submit_rejected", errors=errors, by="host")
                update["outcome"] = {"kind": "failed", "reason": "submit_invalid: " + "; ".join(errors)}
                return update
            ev.emit("submit", **_submit_event(sub))
            if kind == "artifact" and sub["status"] == "done":
                errs = ctx.host_checks(node)
                ev.emit("host_checks", ok=not errs, errors=errs[:50])
                if errs:
                    checks = int(state.get("checks") or 0) + 1
                    update["checks"] = checks
                    if checks > node.flow.max_check_retries:
                        update["outcome"] = {"kind": "failed", "reason": "host_checks_limit: " + "; ".join(errs[:5])}
                        return update
                    update["feedback"] = self._write_feedback(attempt, "host_checks",
                                                              "宿主检查未通过，只改这些问题，其他保持不变：\n"
                                                              + "\n".join(f"- {e}" for e in errs))
                    ev.emit("route", frm=agent, when="checks_failed", to=agent, back_edge_count=checks,
                            max=node.flow.max_check_retries)
                    update["next"] = agent
                    return update
            if kind == "artifact" and sub["status"] == "redo_upstream":
                ev.emit("redo_requested", target=sub["target_node"], artifact=sub["artifact"], field=sub["field"])
            if kind == "verdict" and sub["verdict"] == "reject":
                lead = ("回溯请求未获批准：问题在本节点自行修正，不再请求回溯，只改这些问题：\n"
                        if (executor_last or {}).get("status") == "redo_upstream"
                        else "审核者送回，只改这些问题，其他保持不变：\n")
                start_attempt = attempts.get(node.flow.start, 1)
                update["feedback"] = self._write_feedback(start_attempt, "reviewer", lead + _issues_text(sub["issues"]))
            if kind == "verdict" and sub["verdict"] == "approve_redo_upstream":
                ev.emit("redo_approved", target=(executor_last or {}).get("target_node"), comment=sub.get("comment", ""))
            self._next(agent, sub, state, update)
            return update

        return fn

    def _write_feedback(self, attempt: int, source: str, text: str) -> str:
        path = layout.node_dir(self.ctx.workspace, self.node.run_key) / "feedback" / f"round_{attempt}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"<!-- source: {source} -->\n{text}\n", encoding="utf-8")
        self.ctx.events.emit("feedback_written", attempt=attempt, source=source, path=str(path))
        return text

    def run(self) -> NodeOutcome:
        init: NodeState = {"node": self.node.id, "rev": self.node.rev, "step": 0, "attempts": {}, "last": {},
                           "history": [], "feedback": None, "edges": {}, "checks": 0, "outcome": None}
        limit = self.node.flow.max_steps * 2 + 10
        try:
            final = self.graph.invoke(init, {"recursion_limit": limit})
        except NodeStopped as exc:
            return NodeOutcome("stopped", str(exc))
        except NodeFatal as exc:
            return NodeOutcome("failed", str(exc), fatal=True, code="fatal")
        except TransientTurnError as exc:
            return NodeOutcome("failed", f"transient_error: 重试后仍失败：{exc}", code="transient_error")
        out = final.get("outcome") or {"kind": "failed", "reason": "graph ended without outcome"}
        reason = out.get("reason") or ""
        return NodeOutcome(out["kind"], reason, out.get("redo"), int(final.get("step") or 0),
                           dict(final.get("attempts") or {}), code=out.get("code") or reason.split(":")[0])
