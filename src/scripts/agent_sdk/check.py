"""Live worker check: inspect, then ping through the same run() as the orchestrator."""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from .registry import NAMES, load
from .runtime import WorkerError, emit

PING_PROMPT = "Reply with exactly the word pong. Do not use tools or read files."
DEFAULT_TIMEOUT_S = 60
_ERROR_MARKERS = (
    "MISSING_CREDENTIAL",
    "Model not found",
    "A Gemini API key is required",
    "is not installed",
)


def inspect(name: str) -> tuple[bool, str]:
    key = (name or "").strip().lower()
    if key not in NAMES:
        return False, f"不支持的 Agent：{name}"
    provider = load(key)
    return provider.inspect()


def run(
    name: str,
    prompt: str,
    *,
    cwd: Path,
    stop_event: threading.Event | None = None,
    emit_fn=None,
) -> None:
    provider = load(name)
    provider.run(prompt, cwd=cwd, stop_event=stop_event, emit=emit_fn)


def check(name: str, *, timeout_s: float = DEFAULT_TIMEOUT_S) -> tuple[bool, str]:
    """Inspect then ping. Used as the LCA execution gate."""
    key = (name or "").strip().lower()
    ok, message = inspect(key)
    if not ok:
        return False, message

    collected: list[str] = []
    errors: list[BaseException] = []
    stop_event = threading.Event()

    def _emit(line: str) -> None:
        collected.append(line)
        emit(line)

    def _target() -> None:
        try:
            with tempfile.TemporaryDirectory(prefix=f"agent-sdk-check-{key}-") as temp_dir:
                run(
                    key,
                    PING_PROMPT,
                    cwd=Path(temp_dir),
                    stop_event=stop_event,
                    emit_fn=_emit,
                )
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout_s)
    if thread.is_alive():
        stop_event.set()
        thread.join(5)
        return False, "调用失败"

    if errors:
        exc = errors[0]
        detail = str(exc).strip() or type(exc).__name__
        if isinstance(exc, WorkerError):
            if "not installed" in detail.lower():
                return False, "未安装"
            if "stopped" in detail.lower():
                return False, "调用失败"
        if "无凭据" in detail or "API key" in detail or "MISSING_CREDENTIAL" in detail:
            return False, "无凭据"
        if "Model not found" in detail or "无服务端" in detail:
            return False, "无服务端"
        return False, "调用失败"

    blob = "\n".join(collected)
    if any(marker in blob for marker in _ERROR_MARKERS):
        if "MISSING_CREDENTIAL" in blob or "API key" in blob:
            return False, "无凭据"
        if "Model not found" in blob:
            return False, "无服务端"
        return False, "调用失败"
    return True, "可用"
