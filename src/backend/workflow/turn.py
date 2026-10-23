"""One agent turn: the request the inner graph hands to an AgentDriver and what comes back."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from backend.workflow.config import Node


@dataclass
class TurnResult:
    submit: dict[str, Any] | None = None  # arguments of the fixed submit tool (accepted by the MCP)
    aborted: bool = False
    error: str = ""
    fatal: bool = False  # e.g. model auth failure: stop the whole run
    session_id: str = ""
    nudges: int = 0
    abort_reason: str = ""  # "max_turns" | "timeout" | "too_many_rejections" | "model_error" | "mcp_not_ready" | ""


@dataclass
class TurnRequest:
    node: Node  # the queue item's node (rev resolved)
    agent: str  # agent key in the node
    attempt: int  # this agent's turn number inside the node (1-based)
    prompt: str
    workspace: Path
    run_id: str
    session_key: str  # "<node run_key>.<agent>"
    resume: bool  # continue the same session (artifact agent after reject / host-check failure)
    step: int = 0  # agent turns in this node so far, including this one
    extra: dict[str, Any] = field(default_factory=dict)  # system, submit_context


class AgentDriver(Protocol):
    def run_turn(self, request: TurnRequest) -> TurnResult: ...


# (node, agent, attempt, feedback, specs, context) -> user prompt; context: redo / executor_last / redo_targets
PromptBuilder = Callable[..., str]
