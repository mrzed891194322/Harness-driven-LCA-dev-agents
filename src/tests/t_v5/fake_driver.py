"""Scripted AgentDriver for v5 tests: no model, no pi, writes files like an agent would."""
from __future__ import annotations

from collections.abc import Callable

from backend.v5.access import produce_dir
from backend.v5.runner import TurnRequest, TurnResult


class FakeDriver:
    """``script`` maps (node, role) -> list of actions consumed per turn; default: write + pass."""

    def __init__(self, script: dict | None = None, on_turn: Callable[[TurnRequest], None] | None = None):
        self.script = {k: list(v) for k, v in (script or {}).items()}
        self.calls: list[tuple[str, str, int, bool]] = []
        self.prompts: list[str] = []
        self.systems: list[str] = []
        self.on_turn = on_turn

    def run_turn(self, req: TurnRequest) -> TurnResult:
        self.calls.append((req.node.id, req.role, req.round, req.resume))
        self.prompts.append(req.prompt)
        self.systems.append(req.extra.get("system", ""))
        if self.on_turn:
            self.on_turn(req)
        queue = self.script.get((req.node.id, req.role))
        action = queue.pop(0) if queue else "ok"
        if isinstance(action, TurnResult):
            return action
        art = req.workspace / "artifacts"
        if req.role == "executor":
            if action == "stop":
                return TurnResult(submit={"status": "stop", "summary": "无法完成"})
            for prod in req.node.produces:
                target = art / prod.path
                if target.suffix:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    body = action if action not in ("ok",) else f"{req.node.id} 的产出（第 {req.round} 轮）"
                    target.write_text(body, encoding="utf-8")
                else:
                    (art / produce_dir(prod.path)).mkdir(parents=True, exist_ok=True)
                    (target / "out.md").write_text(f"{req.node.id} 第 {req.round} 轮", encoding="utf-8")
            return TurnResult(submit={"status": "ok", "summary": "done"})
        if action in ("pass", "ok"):
            return TurnResult(submit={"verdict": "pass"})
        if action == "reject":
            return TurnResult(submit={"verdict": "reject", "feedback": "- 第一段太短"})
        return TurnResult(submit={"verdict": action})
