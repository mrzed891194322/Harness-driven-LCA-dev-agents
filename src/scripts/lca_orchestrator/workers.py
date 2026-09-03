"""Worker backends: generic sessions that only receive a prompt."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Protocol

from .codex_events import CodexEventFormatter


class WorkerError(RuntimeError):
    """Worker could not complete the session."""


class WorkerBackend(Protocol):
    name: str

    def run(self, prompt: str, *, cwd: Path, stop_event: threading.Event | None = None) -> None:
        ...


def emit(line: str) -> None:
    sys.stdout.write(line if line.endswith("\n") else line + "\n")
    sys.stdout.flush()


def format_event(*, kind: str, text: str, limit: int = 8000) -> str:
    clipped = text if len(text) <= limit else text[:limit] + "…"
    return f"[{kind}] {clipped}"


def get_backend(name: str) -> WorkerBackend:
    key = (name or "").strip().lower()
    mapping: dict[str, type[WorkerBackend]] = {
        "claude": ClaudeWorker,
        "codex": CodexWorker,
        "opencode": OpenCodeWorker,
        "dsh": DshWorker,
        "antigravity": AntigravityWorker,
    }
    if key not in mapping:
        raise WorkerError(f"unsupported worker: {name}")
    return mapping[key]()


class ClaudeWorker:
    name = "claude"

    def run(self, prompt: str, *, cwd: Path, stop_event: threading.Event | None = None) -> None:
        try:
            from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, query
            from claude_agent_sdk import ClaudeAgentOptions
        except ImportError as exc:
            raise WorkerError("claude-agent-sdk is not installed") from exc

        env = {key: value for key, value in os.environ.items() if key != "ANTHROPIC_API_KEY"}
        options = ClaudeAgentOptions(
            cwd=str(cwd),
            permission_mode="bypassPermissions",
            env=env,
        )

        async def _run() -> None:
            async for message in query(prompt=prompt, options=options):
                if stop_event is not None and stop_event.is_set():
                    raise WorkerError("stopped")
                if isinstance(message, AssistantMessage):
                    for block in getattr(message, "content", []) or []:
                        if isinstance(block, TextBlock):
                            emit(format_event(kind="assistant", text=block.text or ""))
                        elif getattr(block, "type", "") == "tool_use":
                            emit(format_event(kind="tool", text=str(getattr(block, "name", "tool"))))
                elif isinstance(message, ResultMessage):
                    emit(format_event(kind="result", text=str(getattr(message, "subtype", ""))))

        asyncio.run(_run())


class CodexWorker:
    name = "codex"

    def run(self, prompt: str, *, cwd: Path, stop_event: threading.Event | None = None) -> None:
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
            formatter = CodexEventFormatter()
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
                        _emit_codex(formatter, event)
                    return
            result = thread.run(prompt)
            events = getattr(result, "events", None)
            if events is None:
                emit(
                    format_event(
                        kind="assistant",
                        text=str(getattr(result, "final_response", result)),
                    )
                )
                return
            for event in events:
                if stop_event is not None and stop_event.is_set():
                    raise WorkerError("stopped")
                _emit_codex(formatter, event)


class OpenCodeWorker:
    name = "opencode"

    def run(self, prompt: str, *, cwd: Path, stop_event: threading.Event | None = None) -> None:
        try:
            from opencode_ai import Opencode
        except ImportError as exc:
            raise WorkerError("opencode-ai is not installed") from exc

        base_url = os.environ.get("OPENCODE_BASE_URL", "http://127.0.0.1:4096")
        server: subprocess.Popen | None = None
        started_server = False
        if shutil.which("opencode") and not os.environ.get("OPENCODE_BASE_URL"):
            server = subprocess.Popen(
                ["opencode", "serve", "--port", "4096"],
                cwd=str(cwd),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            started_server = True
        client = Opencode(base_url=base_url, timeout=None)
        try:
            _wait_opencode_ready(client, timeout_s=20.0)
            session = _create_opencode_session(client, cwd)
            stream = client.event.list()
            listener = threading.Thread(
                target=_drain_opencode_events,
                args=(stream, stop_event),
                daemon=True,
            )
            listener.start()
            abort_watch = threading.Event()
            watcher = threading.Thread(
                target=_watch_opencode_stop,
                args=(client, session.id, stop_event, abort_watch),
                daemon=True,
            )
            watcher.start()
            try:
                _opencode_chat(client, session.id, prompt)
            finally:
                abort_watch.set()
            if stop_event is not None and stop_event.is_set():
                raise WorkerError("stopped")
        finally:
            if started_server and server is not None:
                try:
                    os.killpg(server.pid, signal.SIGTERM)
                except Exception:
                    server.terminate()


def _wait_opencode_ready(client, *, timeout_s: float) -> None:
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            client.session.list()
            return
        except Exception as exc:
            last_error = exc
            time.sleep(0.25)
    raise WorkerError(f"opencode serve did not become ready: {last_error}")


def _create_opencode_session(client, cwd: Path):
    try:
        return client.session.create(directory=str(cwd))
    except TypeError:
        return client.session.create()


def _opencode_chat(client, session_id: str, prompt: str) -> None:
    parts = [{"type": "text", "text": prompt}]
    provider_id = os.environ.get("OPENCODE_PROVIDER", "opencode")
    model_id = os.environ.get("OPENCODE_MODEL", "default")
    try:
        client.session.chat(
            session_id,
            provider_id=provider_id,
            model_id=model_id,
            parts=parts,
            extra_body={"model": {"providerID": provider_id, "modelID": model_id}},
            timeout=None,
        )
    except TypeError:
        client.session.chat(id=session_id, parts=parts)


def _watch_opencode_stop(client, session_id: str, stop_event: threading.Event | None, done: threading.Event) -> None:
    while not done.is_set():
        if stop_event is not None and stop_event.is_set():
            try:
                client.session.abort(session_id)
            except Exception:
                pass
            return
        time.sleep(0.2)


def _drain_opencode_events(stream, stop_event: threading.Event | None) -> None:
    try:
        for event in stream:
            if stop_event is not None and stop_event.is_set():
                return
            emit(format_event(kind="opencode", text=_jsonish(event)))
    except Exception as exc:
        emit(format_event(kind="error", text=str(exc)))


class DshWorker:
    name = "dsh"

    def run(self, prompt: str, *, cwd: Path, stop_event: threading.Event | None = None) -> None:
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

        def on_notification(note: object) -> None:
            emit(format_event(kind="dsh", text=_jsonish(note)))

        with DeepSeekHarness(**kwargs) as harness:
            session_id = f"lca-{int(time.time())}"
            result = harness.run(
                prompt,
                session_id=session_id,
                on_notification=on_notification,
            )
            if stop_event is not None and stop_event.is_set():
                raise WorkerError("stopped")
            text = getattr(result, "final_response", None)
            if text:
                emit(format_event(kind="assistant", text=str(text)))


class AntigravityWorker:
    name = "antigravity"

    def run(self, prompt: str, *, cwd: Path, stop_event: threading.Event | None = None) -> None:
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
                        emit(format_event(kind="antigravity", text=str(token)))
                        streamed = True
                except TypeError:
                    streamed = False
                if not streamed:
                    text_fn = getattr(response, "text", None)
                    text = await text_fn() if callable(text_fn) else str(response)
                    emit(format_event(kind="assistant", text=str(text)))

        try:
            asyncio.run(_run())
        finally:
            os.chdir(old_cwd)


def _emit_codex(formatter: CodexEventFormatter, event: object) -> None:
    text = formatter.consume(event)
    if text:
        emit(format_event(kind="codex", text=text))


def _jsonish(value: object) -> str:
    if isinstance(value, (str, int, float)):
        return str(value)
    payload = getattr(value, "payload", None)
    if payload is not None and payload is not value:
        try:
            return json.dumps(
                {"method": getattr(value, "method", None), "payload": payload},
                ensure_ascii=False,
                default=str,
            )
        except TypeError:
            pass
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)
