"""Coordinate Pi ModelRuntime.login (OAuth) for the Settings UI.

Uses Pi's AuthInteraction protocol (prompt/notify) bridged over NDJSON events.
See @earendil-works/pi-ai README § Programmatic OAuth.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any

from core.agents.turn_transport import WorkerTransportError
from pi_agents.process import shared_runtime
from services.credentials_service import credentials_dir, credentials_status
from services.project_paths import PROJECT_ROOT


class _LoginSession:
    def __init__(self, login_id: str, provider: str) -> None:
        self.login_id = login_id
        self.provider = provider
        self.events: list[dict[str, Any]] = []
        self.pending_prompt: dict[str, Any] | None = None
        self.done = False
        self.ok: bool | None = None
        self.error: str | None = None
        self.result: dict[str, Any] | None = None
        self.lock = threading.Lock()

    def push(self, kind: str, data: dict[str, Any]) -> None:
        with self.lock:
            self.events.append({"kind": kind, **data})
            if kind == "prompt":
                self.pending_prompt = data
            if kind in {"finished", "failed"}:
                self.done = True


_SESSIONS: dict[str, _LoginSession] = {}
_SESSIONS_LOCK = threading.Lock()


def _get_session(login_id: str) -> _LoginSession | None:
    with _SESSIONS_LOCK:
        return _SESSIONS.get(login_id)


def start_oauth_login(provider: str, *, auth_type: str = "oauth") -> dict[str, Any]:
    name = (provider or "").strip()
    if not name:
        raise ValueError("provider required")
    login_id = uuid.uuid4().hex
    session = _LoginSession(login_id, name)
    with _SESSIONS_LOCK:
        _SESSIONS[login_id] = session

    runtime = shared_runtime(PROJECT_ROOT)
    cred_dir = credentials_dir(PROJECT_ROOT)

    def on_event(event: str, data: dict[str, Any]) -> None:
        if str(data.get("login_id") or "") != login_id:
            return
        if event == "auth.notify":
            session.push("notify", {"event": data.get("event") or {}})
        elif event == "auth.prompt":
            session.push(
                "prompt",
                {
                    "prompt_id": data.get("prompt_id"),
                    "prompt": data.get("prompt") or {},
                },
            )
        elif event == "auth.login_failed":
            session.push("failed", {"message": data.get("message") or "login failed"})
        elif event == "auth.login_finished":
            session.push("finished", {})

    runtime.add_event_handler(on_event)

    def worker() -> None:
        try:
            result = runtime.request(
                "auth.login",
                {
                    "login_id": login_id,
                    "provider": name,
                    "auth_type": auth_type,
                    "credentials_dir": str(cred_dir.resolve()),
                },
                timeout=300.0,
            )
            with session.lock:
                session.ok = True
                session.result = result if isinstance(result, dict) else {"ok": True}
                session.done = True
        except WorkerTransportError as exc:
            with session.lock:
                session.ok = False
                session.error = str(exc)
                session.done = True
            session.push("failed", {"message": str(exc)})
        except Exception as exc:  # noqa: BLE001
            with session.lock:
                session.ok = False
                session.error = str(exc)
                session.done = True
            session.push("failed", {"message": str(exc)})
        finally:
            runtime.remove_event_handler(on_event)

    threading.Thread(target=worker, daemon=True).start()
    return {"login_id": login_id, "provider": name, "auth_type": auth_type}


def login_status(login_id: str) -> dict[str, Any]:
    session = _get_session(login_id)
    if session is None:
        raise ValueError("unknown login_id")
    with session.lock:
        events = list(session.events)
        pending = dict(session.pending_prompt) if session.pending_prompt else None
        return {
            "login_id": session.login_id,
            "provider": session.provider,
            "done": session.done,
            "ok": session.ok,
            "error": session.error,
            "result": session.result,
            "pending_prompt": pending,
            "events": events,
            "providers": credentials_status(PROJECT_ROOT),
        }


def reply_login_prompt(login_id: str, prompt_id: str, value: str) -> dict[str, Any]:
    session = _get_session(login_id)
    if session is None:
        raise ValueError("unknown login_id")
    runtime = shared_runtime(PROJECT_ROOT)
    runtime.request(
        "auth.prompt_reply",
        {"prompt_id": prompt_id, "value": value},
        timeout=30.0,
    )
    with session.lock:
        if session.pending_prompt and session.pending_prompt.get("prompt_id") == prompt_id:
            session.pending_prompt = None
    return {"ok": True}


def logout_provider(provider: str) -> dict[str, Any]:
    name = (provider or "").strip()
    if not name:
        raise ValueError("provider required")
    runtime = shared_runtime(PROJECT_ROOT)
    cred_dir = credentials_dir(PROJECT_ROOT)
    runtime.request(
        "auth.logout",
        {
            "provider": name,
            "credentials_dir": str(cred_dir.resolve()),
        },
        timeout=60.0,
    )
    # Keep Python-side file in sync if runtime wrote only via CredentialStore.
    from services.credentials_service import clear_provider_key, load_pi_auth

    # If logout cleared auth.json, status will reflect it; otherwise clear locally.
    auth = load_pi_auth(PROJECT_ROOT)
    if name in auth:
        clear_provider_key(PROJECT_ROOT, name)
    return {"ok": True, "provider": name, "providers": credentials_status(PROJECT_ROOT)}
