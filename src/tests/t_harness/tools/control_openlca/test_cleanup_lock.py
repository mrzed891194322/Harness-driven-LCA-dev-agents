"""Pre-run cleanup: lock-busy diagnostics and read-timeout retry (p5-cleanup-lock)."""

from __future__ import annotations

import threading

import olca_schema
import pytest
import requests

from harness.tools.shared.control_openlca import cleanup, guard


class _Client:
    def __init__(self, get_failures: int = 0, desc_failures: int = 0) -> None:
        self.get_failures = get_failures
        self.desc_failures = desc_failures
        self.get_calls = 0
        self.desc_calls = 0
        self.delete_calls: list[object] = []

    def get_descriptors(self, model_type):
        self.desc_calls += 1
        if self.desc_failures > 0:
            self.desc_failures -= 1
            raise requests.ReadTimeout("read timed out")
        return []

    def get(self, *_a, **_k):
        raise AssertionError("cleanup must not call full data/get")

    def get_descriptor(self, model_type, entity_id):
        self.get_calls += 1
        if self.get_failures > 0:
            self.get_failures -= 1
            raise requests.ReadTimeout("read timed out")
        return None

    def delete(self, ref):
        self.delete_calls.append(ref)


@pytest.fixture
def probe_ok(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(cleanup, "probe_ipc", lambda h, p: calls.append((h, p)))
    return calls


def test_read_timeout_retries_once_after_health_probe(probe_ok):
    client = _Client(desc_failures=1)
    result = cleanup.collect_entities(
        client, "proj", [olca_schema.Flow], host="h", port=1
    )
    assert result == []
    assert client.desc_calls == 2
    assert probe_ok == [("h", 1)]


def test_read_timeout_twice_fails_with_clear_message(probe_ok):
    client = _Client(get_failures=2)
    with pytest.raises(cleanup.CleanupReadTimeout, match="已重试 1 次仍超时"):
        cleanup._resolve_uuid_targets(
            client, "proj", [("Flow", "f-1")], host="h", port=1
        )
    assert client.get_calls == 2


def test_read_timeout_with_failed_probe_does_not_retry(monkeypatch):
    def bad_probe(h, p):
        raise requests.ConnectTimeout("probe")

    monkeypatch.setattr(cleanup, "probe_ipc", bad_probe)
    client = _Client(get_failures=1)
    with pytest.raises(cleanup.CleanupReadTimeout, match="健康探测也失败"):
        cleanup._resolve_uuid_targets(
            client, "proj", [("Flow", "f-1")], host="h", port=1
        )
    assert client.get_calls == 1


def test_uuid_lookup_timeout_aborts_cleanup_without_delete(
    monkeypatch, tmp_path, probe_ok
):
    client = _Client(get_failures=5)
    monkeypatch.setattr(cleanup, "connect_ipc", lambda *a, **k: client)
    monkeypatch.setattr(cleanup, "close_ipc_client", lambda c: None)
    monkeypatch.setattr(cleanup, "_lci_entity_targets", lambda w: [("Flow", "f-1")])
    result = cleanup.run_cleanup_output(
        "h", 1, "proj", confirm=True, workspace=tmp_path
    )
    assert result["ok"] is False
    assert "读取超时" in result["errors"][0]
    assert client.delete_calls == []


def _hold_lock(operation: str):
    entered = threading.Event()
    release = threading.Event()

    def body(host, port):
        entered.set()
        release.wait(5)
        return {"ok": True}

    runner = guard.serialized_ipc(body, operation=operation)
    thread = threading.Thread(target=runner, args=("127.0.0.1", 18080))
    thread.start()
    assert entered.wait(5)
    return release, thread


def test_lock_holder_reports_other_operation():
    assert guard.endpoint_lock_holder("127.0.0.1", 18080) is None
    release, thread = _hold_lock("cleanup_output_preview")
    try:
        holder = guard.endpoint_lock_holder("127.0.0.1", 18080)
        assert holder is not None
        assert holder.get("operation") == "cleanup_output_preview"
    finally:
        release.set()
        thread.join(5)
    assert guard.endpoint_lock_holder("127.0.0.1", 18080) is None


def test_check_openlca_reports_busy_without_waiting(monkeypatch):
    from backend.services import diagnostics

    def must_not_probe(**kwargs):
        raise AssertionError("health must not wait on a held lock")

    monkeypatch.setattr(diagnostics, "get_openlca_health", must_not_probe)
    release, thread = _hold_lock("import_lci")
    try:
        state = diagnostics.openlca_check("127.0.0.1", 18080)
        assert state["status"] == "busy"
        assert "IPC 正被清理/导入占用" in state["message"]
        assert "导入" in state["message"]
        assert diagnostics.check_openlca("127.0.0.1", 18080) is True
    finally:
        release.set()
        thread.join(5)


def test_check_openlca_endpoint_busy_from_health_is_busy(monkeypatch):
    from backend.services import diagnostics

    def busy(**kwargs):
        raise guard.EndpointBusy("endpoint busy: lock wait exceeded deadline")

    monkeypatch.setattr(diagnostics, "get_openlca_health", busy)
    state = diagnostics.openlca_check("127.0.0.1", 18080)
    assert state["status"] == "busy"
