"""Scripted AgentDriver for v5 tests: no model, no pi, writes files like an agent would."""
from __future__ import annotations

from collections.abc import Callable

from backend.workflow.access import produce_dir
from backend.workflow.turn import TurnRequest, TurnResult

ISSUES = [{"where": "第一段", "problem": "第一段太短", "expected": "至少三句"}]
BLOCK = "上游资料缺少关键数据，本节点无法继续处理。"


def redo(target: str, artifact: str, field: str = "items[0].amount") -> dict:
    return {"status": "redo_upstream", "target_node": target, "artifact": artifact, "field": field,
            "evidence": "原始资料第 3 页写的是 5 kg，上游写成了 50 kg。", "requested_change": "把数量改为 5 kg"}


class FakeDriver:
    """``script`` maps (node, agent) -> actions consumed per turn (key may be "node@rev1").

    executor actions: "ok" (write produces, done), "blocked", a dict (submit as is, files written for done),
    a TurnResult, or any other string (written as the file body, then done).
    reviewer actions: "approve"/"ok", "reject", "terminate", "redo" (approve_redo_upstream), a dict or TurnResult.
    """

    def __init__(self, script: dict | None = None, on_turn: Callable[[TurnRequest], None] | None = None):
        self.script = {k: list(v) for k, v in (script or {}).items()}
        self.calls: list[tuple[str, str, int, bool]] = []
        self.reqs: list[TurnRequest] = []
        self.prompts: list[str] = []
        self.systems: list[str] = []
        self.on_turn = on_turn

    def _action(self, req: TurnRequest):
        for key in ((req.node.run_key, req.agent), (req.node.id, req.agent)):
            queue = self.script.get(key)
            if queue:
                return queue.pop(0)
        return "ok"

    def _write(self, req: TurnRequest, body: str | None) -> None:
        art = req.workspace / "artifacts"
        for prod in req.node.produces:
            target = art / prod.path
            if target.suffix:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body or f"{req.node.run_key} 的产出（第 {req.attempt} 轮）", encoding="utf-8")
            else:
                (art / produce_dir(prod.path)).mkdir(parents=True, exist_ok=True)
                target.mkdir(parents=True, exist_ok=True)
                (target / "out.md").write_text(f"{req.node.run_key} 第 {req.attempt} 轮", encoding="utf-8")

    def run_turn(self, req: TurnRequest) -> TurnResult:
        self.calls.append((req.node.run_key, req.agent, req.attempt, req.resume))
        self.reqs.append(req)
        self.prompts.append(req.prompt)
        self.systems.append(req.extra.get("system", ""))
        if self.on_turn:
            self.on_turn(req)
        action = self._action(req)
        if isinstance(action, TurnResult):
            return action
        done = {"status": "done", "summary": "done", "artifacts": [p.path for p in req.node.produces]}
        if req.node.kind(req.agent) == "artifact":
            if action == "blocked":
                return TurnResult(submit={"status": "blocked", "reason": BLOCK})
            if isinstance(action, dict):
                if action.get("status") == "done":
                    self._write(req, None)
                return TurnResult(submit=action)
            self._write(req, None if action == "ok" else action)
            return TurnResult(submit=done)
        if isinstance(action, dict):
            return TurnResult(submit=action)
        if action in ("approve", "ok"):
            return TurnResult(submit={"verdict": "approve"})
        if action == "reject":
            return TurnResult(submit={"verdict": "reject", "issues": ISSUES})
        if action == "terminate":
            return TurnResult(submit={"verdict": "terminate", "reason": "交付物与计划完全不符，无法通过返工修正。"})
        if action == "redo":
            return TurnResult(submit={"verdict": "approve_redo_upstream", "comment": "符合判据"})
        return TurnResult(submit={"verdict": action})
