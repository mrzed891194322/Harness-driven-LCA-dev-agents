from __future__ import annotations

import shutil
import sys
import threading
from pathlib import Path

from ...runtime import WorkerError, format_event, resolve_emit


def _codex_formatter():
    scripts = Path(__file__).resolve().parents[3]
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from lca_orchestrator.codex_events import CodexEventFormatter

    return CodexEventFormatter()


def run(
    prompt: str,
    *,
    cwd: Path,
    stop_event: threading.Event | None = None,
    emit=None,
) -> None:
    write = resolve_emit(emit)
    try:
        from openai_codex import Codex, Sandbox
    except ImportError as exc:
        raise WorkerError("openai-codex is not installed") from exc

    kwargs: dict[str, object] = {}
    bin_path = shutil.which("codex")
    try:
        from openai_codex import CodexConfig

        if bin_path:
            kwargs["config"] = CodexConfig(codex_bin=bin_path)
    except Exception:
        kwargs = {}

    formatter = _codex_formatter()
    with Codex(**kwargs) as codex:
        start_kwargs: dict[str, object] = {"cwd": str(cwd)}
        try:
            start_kwargs["sandbox"] = Sandbox.workspace_write
        except Exception:
            pass
        try:
            from openai_codex import ApprovalMode

            start_kwargs["approval_mode"] = ApprovalMode.auto_review
        except Exception:
            pass
        thread = codex.thread_start(**start_kwargs)
        turn = getattr(thread, "turn", None)
        if callable(turn):
            handle = turn(prompt)
            stream = getattr(handle, "stream", None)
            if callable(stream):
                for event in stream():
                    if stop_event is not None and stop_event.is_set():
                        interrupt = getattr(handle, "interrupt", None)
                        if callable(interrupt):
                            interrupt()
                        raise WorkerError("stopped")
                    text = formatter.consume(event)
                    if text:
                        write(format_event(kind="codex", text=text))
                return
        result = thread.run(prompt)
        events = getattr(result, "events", None)
        if events is None:
            write(
                format_event(
                    kind="assistant",
                    text=str(getattr(result, "final_response", result)),
                )
            )
            return
        for event in events:
            if stop_event is not None and stop_event.is_set():
                raise WorkerError("stopped")
            text = formatter.consume(event)
            if text:
                write(format_event(kind="codex", text=text))
