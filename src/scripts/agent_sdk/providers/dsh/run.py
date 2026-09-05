from __future__ import annotations

import os
import shutil
import threading
import time
from pathlib import Path

from ...runtime import WorkerError, format_event, jsonish, resolve_emit


def run(
    prompt: str,
    *,
    cwd: Path,
    stop_event: threading.Event | None = None,
    emit=None,
) -> None:
    write = resolve_emit(emit)
    try:
        from deepseek_harness import DeepSeekHarness
    except ImportError as exc:
        raise WorkerError("deepseek-harness-sdk is not installed") from exc

    os.environ.setdefault("DSH_PERMISSION_MODE", "danger-full-access")
    dsh_home = os.environ.get("DSH_HOME") or str(cwd / ".dsh" / "sdk-home")
    Path(dsh_home).mkdir(parents=True, exist_ok=True)
    patch = cwd / ".dsh" / "cordis.patch.yml"
    kwargs: dict[str, object] = {
        "dsh_home": dsh_home,
        "cwd": str(cwd),
        "profile": "sdk",
    }
    if patch.is_file():
        kwargs["patches"] = (str(patch),)
    bin_path = shutil.which("dsh")
    if bin_path:
        kwargs["dsh_bin"] = bin_path

    notes: list[str] = []

    def on_notification(note: object) -> None:
        text = jsonish(note)
        notes.append(text)
        write(format_event(kind="dsh", text=text))

    with DeepSeekHarness(**kwargs) as harness:
        session_id = f"lca-{int(time.time())}"
        result = harness.run(
            prompt,
            session_id=session_id,
            on_notification=on_notification,
        )
        if stop_event is not None and stop_event.is_set():
            raise WorkerError("stopped")
        blob = "\n".join(notes)
        if "MISSING_CREDENTIAL" in blob:
            raise WorkerError("MISSING_CREDENTIAL")
        error = getattr(result, "error", None) or getattr(result, "failure", None)
        if error:
            raise WorkerError(str(error))
        text = getattr(result, "final_response", None)
        if text:
            write(format_event(kind="assistant", text=str(text)))
