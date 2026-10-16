"""pi-runtime model_connection turn result -> WorkerTransportError (retryable)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from backend.core.agents.session import SessionConfig, SessionRef, WorkerTransportError
from backend.pi_client.client import PiRuntimeSessionClient
from backend.pi_client.process import runtime_error
from tests.t_core.test_pi_activity import _spec


class _Runtime:
    project_root = Path(".")

    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result

    def add_event_handler(self, handler: Any) -> None:
        pass

    def remove_event_handler(self, handler: Any) -> None:
        pass

    def request(self, method: str, params: dict[str, Any], *, timeout: float) -> Any:
        return self.result


def _turn(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, result: dict[str, Any]):
    monkeypatch.setattr("backend.pi_client.client.shared_runtime", lambda root=None: _Runtime(result))
    client = PiRuntimeSessionClient(tmp_path)
    config = SessionConfig(worker="pi", cwd=tmp_path, tmp_dir=tmp_path, launch_spec=_spec(tmp_path))
    ref = SessionRef(platform="pi", session_id="s", storage={"session_key": "k"})
    return client.run_turn(ref, "go", config)


def test_model_connection_result_raises_transport_error(monkeypatch, tmp_path) -> None:
    outcome = {"stop_reason": "error", "error_kind": "connection", "tool_calls": 0, "retries": 4}
    with pytest.raises(WorkerTransportError) as info:
        _turn(monkeypatch, tmp_path, {
            "status": "error", "kind": "model_connection", "message": "Connection error.",
            "outcome": outcome, "started_at": "a", "ended_at": "b",
        })
    assert "模型连接失败" in str(info.value)
    assert "Connection error." in str(info.value)
    assert info.value.outcome["retries"] == 4
    assert info.value.outcome["started_at"] == "a"


def test_ok_result_carries_outcome(monkeypatch, tmp_path) -> None:
    result = _turn(monkeypatch, tmp_path, {"status": "ok", "text": "t", "outcome": {"tool_calls": 3}})
    assert result.outcome == {"tool_calls": 3}


@pytest.mark.parametrize("msg", ["Connection error.", "connection reset by peer", "other side closed",
                                 "Service Unavailable"])
def test_transient_regex_safety_net(msg: str) -> None:
    assert isinstance(runtime_error(msg), WorkerTransportError)


def test_non_transient_runtime_error_not_retried() -> None:
    assert not isinstance(runtime_error("unknown session k"), WorkerTransportError)
