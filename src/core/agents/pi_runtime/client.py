"""SessionClient backed by Node Pi SDK runtime."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

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
        session_key = f"{config.run_id}:{config.stage_id}:{config.role}:{config.attempt}"
        spec = self._launch_specs.get(session_key)
        if spec is None:
            raise SessionResumeError("缺少 SessionLaunchSpec，无法创建 Pi SDK 会话")
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
        session_key = saved.storage.get("session_key") or ""
        spec = self._launch_specs.get(session_key)
        if spec is None:
            raise SessionResumeError("缺少 SessionLaunchSpec，无法恢复 Pi SDK 会话")
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
        del config
        session_key = ref.storage.get("session_key") or ""
        result = self._runtime.request(
            "session.run_turn",
            {"session_key": session_key, "prompt": prompt},
            timeout=7200.0,
        )
        text = str(result.get("text") or "")
        status = str(result.get("status") or "ok")
        ref.last_turn_status = status
        return TurnResult(status=status, session_ref=ref, text=text)

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
