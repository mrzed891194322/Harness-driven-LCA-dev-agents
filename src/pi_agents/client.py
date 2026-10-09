"""SessionClient backed by Node Pi SDK runtime."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.agents.activity import activity_log_path, append_activity
from core.agents.progress import format_assistant, format_tool_end, format_tool_start, print_session
from core.agents.providers.store import StoredSessionProvider, session_dir, write_ref
from core.agents.session import SessionConfig, SessionRef, SessionResumeError, TurnResult
from core.contracts.session_launch_spec import SessionLaunchSpec

from .process import shared_runtime


class PiRuntimeSessionClient(StoredSessionProvider):
    worker = "pi"

    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = project_root
        self._runtime = shared_runtime(project_root)
        self._launch_specs: dict[str, SessionLaunchSpec] = {}

    def attach_launch_spec(self, session_key: str, spec: SessionLaunchSpec) -> None:
        self._launch_specs[session_key] = spec

    def create(self, config: SessionConfig) -> SessionRef:
        session_id = uuid.uuid4().hex
        storage_dir = session_dir(config.tmp_dir, self.worker, session_id)
        storage_dir.mkdir(parents=True, exist_ok=True)
        spec = config.launch_spec
        if spec is None:
            raise SessionResumeError("缺少 SessionLaunchSpec，无法创建 Pi SDK 会话")
        session_key = spec.session_key
        self._launch_specs[session_key] = spec
        result = self._runtime.request(
            "session.create",
            {"launch_spec": spec.to_dict()},
            timeout=120.0,
        )
        storage = {
            "dir": str(storage_dir),
            "session_key": session_key,
            "pi_session_id": str(result.get("pi_session_id") or ""),
            "session_file": spec.session_storage.get("session_file", ""),
            "agent_dir": spec.session_storage.get("agent_dir", ""),
            "bundle_hash": spec.bundle_hash,
        }
        ref = SessionRef(platform=self.worker, session_id=session_id, storage=storage)
        write_ref(storage_dir, ref)
        return ref

    def resume(self, ref: SessionRef, config: SessionConfig) -> SessionRef:
        saved = super().resume(ref, config)
        spec = config.launch_spec
        if spec is None:
            raise SessionResumeError("缺少 SessionLaunchSpec，无法恢复 Pi SDK 会话")
        session_key = spec.session_key
        stored_key = saved.storage.get("session_key") or ""
        if stored_key and stored_key != session_key:
            raise SessionResumeError(
                f"会话键不一致：已存 {stored_key}，当前 {session_key}"
            )
        self._launch_specs[session_key] = spec
        session_file = saved.storage.get("session_file") or spec.session_storage.get(
            "session_file", ""
        )
        if session_file and not Path(session_file).is_file():
            raise SessionResumeError("Pi SDK 会话文件不存在")
        self._runtime.request(
            "session.resume",
            {
                "session_key": session_key,
                "launch_spec": spec.to_dict(),
            },
            timeout=120.0,
        )
        return saved

    def run_turn(
        self,
        ref: SessionRef,
        prompt: str,
        config: SessionConfig,
    ) -> TurnResult:
        session_key = ref.storage.get("session_key") or ""
        spec = config.launch_spec or self._launch_specs.get(session_key)
        handler = self._activity_handler(session_key, spec)
        if handler is not None:
            self._runtime.add_event_handler(handler)
        try:
            result = self._runtime.request(
                "session.run_turn",
                {"session_key": session_key, "prompt": prompt},
                timeout=7200.0,
            )
        finally:
            if handler is not None:
                self._runtime.remove_event_handler(handler)
        text = str(result.get("text") or "")
        status = str(result.get("status") or "ok")
        ref.last_turn_status = status
        return TurnResult(status=status, session_ref=ref, text=text)

    def _activity_handler(
        self, session_key: str, spec: SessionLaunchSpec | None
    ) -> Callable[[str, dict[str, Any]], None] | None:
        """Mirror ``turn.event`` runtime events to events.jsonl and progress.txt."""
        if not session_key or spec is None or not spec.run_id:
            return None
        root = Path(
            spec.resource_bindings.get("project_root")
            or self._project_root
            or self._runtime.project_root
        )
        try:
            path = activity_log_path(root, spec.run_id)
        except ValueError:
            return None
        tags = {
            "run_id": spec.run_id,
            "stage": spec.stage_id,
            "role": spec.role,
            "assignment": spec.assignment_id,
            "attempt": spec.attempt,
            "worker": self.worker,
        }

        def on_event(name: str, data: dict[str, Any]) -> None:
            if name != "turn.event" or data.get("session_key") != session_key:
                return
            record = {**tags, **{k: v for k, v in data.items() if k != "session_key"}}
            record["session_key"] = session_key
            try:
                append_activity(path, record)
            except OSError:
                pass
            line = activity_progress_line(record)
            if line:
                print_session(
                    spec.stage_id, spec.role, self.worker, line, attempt=spec.attempt
                )

        return on_event

    def release(self, ref: SessionRef) -> None:
        session_key = ref.storage.get("session_key") or ""
        if session_key:
            try:
                self._runtime.request(
                    "session.release", {"session_key": session_key}, timeout=30.0
                )
            except Exception:
                pass
        super().release(ref)


def activity_progress_line(record: dict[str, Any]) -> str:
    """Render one activity record in the tagged progress.txt format the run page parses."""
    kind = record.get("kind")
    tool = str(record.get("tool") or "")
    args = record.get("args") if isinstance(record.get("args"), dict) else {}
    if kind == "tool_call":
        return format_tool_start(tool, args) if args else (
            f"→ {tool} {record.get('summary') or ''}".rstrip()
        )
    if kind == "tool_result":
        error = (record.get("summary") or "工具报错") if record.get("is_error") else None
        return format_tool_end(tool, args, error=error)
    if kind == "text":
        return format_assistant(str(record.get("summary") or ""))
    if kind == "turn_end" and record.get("is_error"):
        return f"error: {record.get('summary') or 'turn failed'}"
    return ""
