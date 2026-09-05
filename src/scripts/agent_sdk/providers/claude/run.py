from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path

from ...runtime import WorkerError, format_event, resolve_emit
from .config import NAME


def run(
    prompt: str,
    *,
    cwd: Path,
    stop_event: threading.Event | None = None,
    emit=None,
) -> None:
    write = resolve_emit(emit)
    try:
        from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, query
        from claude_agent_sdk import ClaudeAgentOptions
    except ImportError as exc:
        raise WorkerError("claude-agent-sdk is not installed") from exc

    options = ClaudeAgentOptions(
        cwd=str(cwd),
        permission_mode="bypassPermissions",
        env=dict(os.environ),
    )

    async def _run() -> None:
        async for message in query(prompt=prompt, options=options):
            if stop_event is not None and stop_event.is_set():
                raise WorkerError("stopped")
            if isinstance(message, AssistantMessage):
                for block in getattr(message, "content", []) or []:
                    if isinstance(block, TextBlock):
                        write(format_event(kind="assistant", text=block.text or ""))
                    elif getattr(block, "type", "") == "tool_use":
                        write(format_event(kind="tool", text=str(getattr(block, "name", "tool"))))
            elif isinstance(message, ResultMessage):
                subtype = str(getattr(message, "subtype", "") or "")
                write(format_event(kind="result", text=subtype))
                if subtype and subtype not in {"success", "result"}:
                    raise WorkerError(f"{NAME} ping failed: {subtype}")

    asyncio.run(_run())
