"""Per-request IPC timeouts, fail-fast budget, and unresponsive handling (fakes only)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

from harness.tools.shared.control_openlca import guard, operations
from harness.tools.shared.control_openlca.connection import (
    _TimeoutHTTPAdapter,
    session_request_timeout,
)
from harness.tools.shared.control_openlca.diagnostics import capture_openlca_timeout_diagnostics
from harness.tools.shared.control_openlca.guard import endpoint_uncertain_marker
from harness.tools.shared.control_openlca.ipc_failure import (
    NON_RETRYABLE_KIND,
    on_ipc_transport_failure,
)
from harness.tools.shared.control_openlca.run_events import activity_log_path
from harness.tools.shared.control_openlca.timeout_policy import resolve_http_read_timeout
from tests.support.openlca_fakes import FakeClient


def test_resolve_http_read_timeout_never_below_configured_read(tmp_path, monkeypatch):
    monkeypatch.setenv("LCA_IPC_LOCK_ROOT", str(tmp_path / "locks"))
    monkeypatch.setenv("OPENLCA_TIMEOUT_REQUEST_S", "120")
    with guard.endpoint_guard("localhost", 8080, budget_sec=3600):
        connect, read = resolve_http_read_timeout(read_sec=120.0)
    assert connect == 2.0
    assert read == 120.0


def test_resolve_http_read_timeout_fails_fast_on_tiny_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("LCA_IPC_LOCK_ROOT", str(tmp_path / "locks"))
    with guard.endpoint_guard("localhost", 8080, budget_sec=3600):
        guard._local.deadline = time.monotonic() + 0.5
        with pytest.raises(requests.Timeout, match="fail fast"):
            resolve_http_read_timeout(read_sec=120.0)


def test_session_request_timeout_uses_per_request_read(tmp_path, monkeypatch):
    monkeypatch.setenv("LCA_IPC_LOCK_ROOT", str(tmp_path / "locks"))
    monkeypatch.setenv("OPENLCA_TIMEOUT_REQUEST_S", "90")
    timeout = session_request_timeout()
    assert timeout == (2.0, 90.0)


def test_adapter_applies_fail_fast_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("LCA_IPC_LOCK_ROOT", str(tmp_path / "locks"))
    adapter = _TimeoutHTTPAdapter((2.0, 120.0))
    with guard.endpoint_guard("localhost", 8080, budget_sec=10):
        guard._local.deadline = time.monotonic() + 0.2
        with pytest.raises(requests.Timeout):
            adapter.send(object(), timeout=(2.0, 120.0))


def test_on_ipc_transport_failure_writes_event_and_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setenv("LCA_IPC_LOCK_ROOT", str(tmp_path / "locks"))
    run_id = "run-timeout-test"
    run_dir = tmp_path / ".local" / "runs" / run_id
    run_dir.mkdir(parents=True)
    with patch(
        "harness.tools.shared.control_openlca.ipc_failure.health_probe_responsive",
        return_value=(False, "timeout"),
    ):
        with patch(
            "harness.tools.shared.control_openlca.diagnostics._ss_port_snapshot",
            return_value="ss-output",
        ):
            payload = on_ipc_transport_failure(
                "127.0.0.1",
                8080,
                requests.Timeout("read timed out"),
                operation="import",
                entity={"path": "a.json", "entity_type": "ProductSystem", "name": "x", "id": "1"},
                run_id=run_id,
                project_root=tmp_path,
            )
    assert payload["retryable"] is False
    assert payload["error_kind"] == NON_RETRYABLE_KIND
    events = activity_log_path(tmp_path, run_id).read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(events[-1])["kind"] == NON_RETRYABLE_KIND
    diag_files = list((run_dir / "diagnostics").glob("openlca_timeout_*.json"))
    assert diag_files


def test_uncertain_leftover_rejects_import(monkeypatch, tmp_path):
    monkeypatch.setenv("LCA_IPC_LOCK_ROOT", str(tmp_path / "locks"))
    marker = endpoint_uncertain_marker("127.0.0.1", 8080)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("{}", encoding="utf-8")
    client = FakeClient()
    entity_id = "11111111-1111-1111-1111-111111111111"
    workspace = tmp_path / "workspace"
    lci_dir = workspace / "outputs" / "LCI"
    lci_dir.mkdir(parents=True)
    journal = workspace / "records" / "import-operations"
    journal.mkdir(parents=True, exist_ok=True)
    preflight_id = "pf-1"
    run_id = "run-uncertain"
    identity = {
        "run_id": run_id,
        "endpoint": "http://127.0.0.1:8080",
        "database_name": "db",
        "category": "cat",
        "lci_dir": str(lci_dir),
    }
    from harness.tools.shared.control_openlca import workflow as wflow

    identity["lci_content"] = wflow.stable_hash({})
    (journal / "preflights").mkdir(parents=True, exist_ok=True)
    (journal / "preflights" / f"{preflight_id}.json").write_text(
        json.dumps(
            {
                "ok": True,
                "preflight_hash": "h",
                "identity": identity,
            }
        ),
        encoding="utf-8",
    )
    with patch(
        "harness.tools.shared.control_openlca.operations.create_ipc_client",
        return_value=client,
    ):
        with patch(
            "harness.tools.shared.control_openlca.workflow._inspect_import",
            return_value=(
                {"ok": True, "preflight_hash": "h"},
                [
                    {
                        "path": "product_systems/x.json",
                        "entity_type": "ProductSystem",
                        "id": entity_id,
                        "name": "sys",
                        "data": {},
                    }
                ],
                [],
            ),
        ):
            with patch(
                "harness.tools.shared.control_openlca.workflow.find_uncertain_leftover_entities",
                return_value=[
                    {
                        "path": "product_systems/x.json",
                        "entity_type": "ProductSystem",
                        "id": entity_id,
                        "name": "sys",
                    }
                ],
            ):
                result = operations.import_request(
                    "127.0.0.1",
                    8080,
                    workspace / "outputs" / "LCI",
                    "cat",
                    "db",
                    run_id=run_id,
                    request_id="req-1",
                    preflight_id=preflight_id,
                    operation_dir=journal,
                    client=client,
                )
    assert result["status"] == "rejected"
    assert result["retryable"] is False


def test_capture_diagnostics_never_raises(tmp_path):
    path = capture_openlca_timeout_diagnostics(
        tmp_path / "run",
        host="127.0.0.1",
        port=8080,
        context={"note": "test"},
    )
    assert path is not None
    assert path.is_file()
