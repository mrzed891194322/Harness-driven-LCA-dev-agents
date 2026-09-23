"""Serializable session storage under workspace/tmp."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from ..mcp import tool_entry_to_mcp
from ..session import SessionConfig, SessionRef, SessionResumeError


class StoredSessionProvider:
    worker: str = ""

    def create(self, config: SessionConfig) -> SessionRef:
        session_id = uuid.uuid4().hex
        storage_dir = session_dir(config.tmp_dir, self.worker, session_id)
        storage_dir.mkdir(parents=True, exist_ok=True)
        storage = {"dir": str(storage_dir)}
        storage.update(self._create_storage(config, storage_dir, session_id))
        ref = SessionRef(platform=self.worker, session_id=session_id, storage=storage)
        write_ref(storage_dir, ref)
        return ref

    def resume(self, ref: SessionRef, config: SessionConfig) -> SessionRef:
        storage_dir = Path(ref.storage.get("dir") or "")
        if not storage_dir.is_dir() or not (storage_dir / "ref.json").is_file():
            raise SessionResumeError(
                f"{self.worker} 会话存储缺失，无法续接 {ref.session_id}"
            )
        saved = SessionRef.from_dict(
            json.loads((storage_dir / "ref.json").read_text(encoding="utf-8"))
        )
        if saved.session_id != ref.session_id:
            raise SessionResumeError(
                "会话 ID 与存储不一致，不能把同名新会话视为恢复成功"
            )
        self._assert_native_storage(saved, config)
        return saved

    def release(self, ref: SessionRef) -> None:
        del ref

    def _create_storage(
        self,
        config: SessionConfig,
        storage_dir: Path,
        session_id: str,
    ) -> dict[str, str]:
        del config, storage_dir, session_id
        return {}

    def _assert_native_storage(self, ref: SessionRef, config: SessionConfig) -> None:
        del ref, config


def session_dir(tmp_dir: Path, worker: str, session_id: str) -> Path:
    return tmp_dir / "sdk-sessions" / worker / session_id


def write_ref(storage_dir: Path, ref: SessionRef) -> None:
    (storage_dir / "ref.json").write_text(
        json.dumps(ref.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_stdio_mcp_snippet(mcp_servers: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {name: tool_entry_to_mcp(name, spec) for name, spec in mcp_servers.items()}
