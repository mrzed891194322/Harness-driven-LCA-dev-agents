from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path

from ...runtime import WorkerError, format_event, resolve_emit


def run(
    prompt: str,
    *,
    cwd: Path,
    stop_event: threading.Event | None = None,
    emit=None,
) -> None:
    write = resolve_emit(emit)
    try:
        from google.antigravity import Agent, LocalAgentConfig
    except ImportError as exc:
        raise WorkerError("google-antigravity is not installed") from exc

    config_kwargs: dict[str, object] = {}
    try:
        from google.antigravity import policy

        config_kwargs["policies"] = [policy.allow_all()]
    except Exception:
        pass
    use_vertex = (os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if use_vertex:
        config_kwargs["vertex"] = True
        project = (os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip()
        location = (os.environ.get("GOOGLE_CLOUD_LOCATION") or "").strip()
        if project:
            config_kwargs["project"] = project
        if location:
            config_kwargs["location"] = location
    try:
        config = LocalAgentConfig(cwd=str(cwd), **config_kwargs)
    except TypeError:
        config = LocalAgentConfig(**config_kwargs)

    old_cwd = os.getcwd()
    os.chdir(cwd)

    async def _run() -> None:
        async with Agent(config) as agent:
            response = await agent.chat(prompt)
            streamed = False
            try:
                async for token in response:
                    if stop_event is not None and stop_event.is_set():
                        raise WorkerError("stopped")
                    write(format_event(kind="antigravity", text=str(token)))
                    streamed = True
            except TypeError:
                streamed = False
            if not streamed:
                text_fn = getattr(response, "text", None)
                text = await text_fn() if callable(text_fn) else str(response)
                write(format_event(kind="assistant", text=str(text)))

    try:
        asyncio.run(_run())
    finally:
        os.chdir(old_cwd)
