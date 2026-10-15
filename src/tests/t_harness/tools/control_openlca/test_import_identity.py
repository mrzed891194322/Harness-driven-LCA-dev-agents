from __future__ import annotations

import olca_schema
import pytest
from unittest.mock import MagicMock, patch

from harness.tools.shared.control_openlca import guard, operations
from harness.tools.shared.control_openlca.guard import endpoint_uncertain_marker
from tests.support.openlca_fakes import (
    FLOW_ID,
    FakeImportClient,
    PROCESS_ID,
    PRODUCT_SYSTEM_ID,
    write_flow,
    write_product_system_fixture,
)


@pytest.fixture
def lock_root(tmp_path, monkeypatch):
    monkeypatch.setenv("LCA_IPC_LOCK_ROOT", str(tmp_path / "locks"))


@pytest.fixture(autouse=True)
def _mock_bounded_ipc_probe():
    """Guard re-probes IPC when an uncertain marker exists; no openLCA in CI."""
    with (
        patch.object(guard, "probe_ipc", return_value=MagicMock()),
        patch.object(guard, "close_ipc_client"),
    ):
        yield


def test_guard_self_marker_not_prior_uncertain(lock_root):
    with guard.endpoint_guard("127.0.0.1", 8080):
        assert guard.prior_uncertain_marker("127.0.0.1", 8080) is False
        assert guard.endpoint_is_uncertain("127.0.0.1", 8080) is True


def test_guard_stale_marker_is_prior_uncertain(lock_root):
    marker = endpoint_uncertain_marker("127.0.0.1", 8080)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"pid": 1}', encoding="utf-8")
    with guard.endpoint_guard("127.0.0.1", 8080):
        assert guard.prior_uncertain_marker("127.0.0.1", 8080) is True


def _start_import(tmp_path, client, run_id="run-one"):
    workspace = tmp_path / "workspace"
    lci = workspace / "outputs" / "LCI"
    write_product_system_fixture(lci)
    operation_dir = workspace / "runs" / "04-openlca-reporting" / "executor-1" / "import-operations"
    preflight = operations.preflight(
        "localhost",
        8080,
        lci,
        "project-a",
        "isolated-db",
        run_id=run_id,
        operation_dir=operation_dir,
        client=client,
    )
    assert preflight["ok"]
    return lci, {
        "run_id": run_id,
        "request_id": "request-one",
        "preflight_id": preflight["preflight_id"],
        "operation_dir": operation_dir,
        "client": client,
    }


def test_reimport_same_id_does_not_duplicate_entity_plan(lock_root, tmp_path):
    client = FakeImportClient()
    lci, kwargs = _start_import(tmp_path, client)
    first = operations.import_request(
        "localhost", 8080, lci, "project-a", "isolated-db", **kwargs
    )
    assert first["status"] == "success"
    plan_ids = [entry["id"] for entry in first.get("entity_plan") or []]
    assert len(plan_ids) == len(set(plan_ids))
    second = operations.import_request(
        "localhost",
        8080,
        lci,
        "project-a",
        "isolated-db",
        run_id=kwargs["run_id"],
        request_id="request-one",
        preflight_id=kwargs["preflight_id"],
        operation_dir=kwargs["operation_dir"],
        client=client,
    )
    assert second.get("reuse_reason")
    plan2 = [entry["id"] for entry in second.get("entity_plan") or []]
    assert len(plan2) == len(set(plan2))


def test_same_run_reimport_after_content_change_updates(lock_root, tmp_path):
    client = FakeImportClient()
    lci, kwargs = _start_import(tmp_path, client)
    first = operations.import_request(
        "localhost", 8080, lci, "project-a", "isolated-db", **kwargs
    )
    assert first["status"] == "success"
    puts_after_first = len(client.put_calls)

    write_flow(lci, name="Updated foreground flow")
    preflight2 = operations.preflight(
        "localhost",
        8080,
        lci,
        "project-a",
        "isolated-db",
        run_id=kwargs["run_id"],
        operation_dir=kwargs["operation_dir"],
        client=client,
    )
    with guard.endpoint_guard("localhost", 8080):
        second = operations.import_request(
            "localhost",
            8080,
            lci,
            "project-a",
            "isolated-db",
            run_id=kwargs["run_id"],
            request_id="request-two",
            preflight_id=preflight2["preflight_id"],
            operation_dir=kwargs["operation_dir"],
            client=client,
        )
    assert second["status"] == "success"
    assert second["operation_id"] != first["operation_id"]
    assert second.get("superseded_operation_id") == first["operation_id"]
    assert len(client.put_calls) > puts_after_first


def test_foreign_leftover_blocked_only_with_prior_uncertain_marker(lock_root, tmp_path):
    client = FakeImportClient()
    client.entities[(olca_schema.ProductSystem, PRODUCT_SYSTEM_ID)] = (
        olca_schema.ProductSystem(
            id=PRODUCT_SYSTEM_ID,
            name="Leftover system",
            category="project-a",
        )
    )
    lci, kwargs = _start_import(tmp_path, client)
    marker = endpoint_uncertain_marker("localhost", 8080)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"pid": 1}', encoding="utf-8")
    preflight = operations.preflight(
        "localhost",
        8080,
        lci,
        "project-a",
        "isolated-db",
        run_id=kwargs["run_id"],
        operation_dir=kwargs["operation_dir"],
        client=client,
    )
    with guard.endpoint_guard("localhost", 8080):
        result = operations.import_request(
            "localhost",
            8080,
            lci,
            "project-a",
            "isolated-db",
            run_id=kwargs["run_id"],
            request_id="request-foreign",
            preflight_id=preflight["preflight_id"],
            operation_dir=kwargs["operation_dir"],
            client=client,
        )
    assert result["status"] == "rejected"
    assert result.get("retryable") is False


def test_same_run_owned_leftover_allowed_with_prior_marker(lock_root, tmp_path):
    client = FakeImportClient()
    lci, kwargs = _start_import(tmp_path, client)
    first = operations.import_request(
        "localhost", 8080, lci, "project-a", "isolated-db", **kwargs
    )
    assert first["status"] == "success"
    marker = endpoint_uncertain_marker("localhost", 8080)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"pid": 1}', encoding="utf-8")
    write_flow(lci, name="Updated foreground flow")
    preflight2 = operations.preflight(
        "localhost",
        8080,
        lci,
        "project-a",
        "isolated-db",
        run_id=kwargs["run_id"],
        operation_dir=kwargs["operation_dir"],
        client=client,
    )
    with guard.endpoint_guard("localhost", 8080):
        second = operations.import_request(
            "localhost",
            8080,
            lci,
            "project-a",
            "isolated-db",
            run_id=kwargs["run_id"],
            request_id="request-two",
            preflight_id=preflight2["preflight_id"],
            operation_dir=kwargs["operation_dir"],
            client=client,
        )
    assert second["status"] == "success"


def test_resume_with_changed_content_reimports_only_changed(lock_root, tmp_path):
    client = FakeImportClient()
    lci, kwargs = _start_import(tmp_path, client)
    first = operations.import_request(
        "localhost", 8080, lci, "project-a", "isolated-db", **kwargs
    )
    assert first["status"] == "success"
    write_flow(lci, name="Updated foreground flow")
    preflight2 = operations.preflight(
        "localhost",
        8080,
        lci,
        "project-a",
        "isolated-db",
        run_id=kwargs["run_id"],
        operation_dir=kwargs["operation_dir"],
        client=client,
    )
    resumed = operations.resume_import_request(
        "localhost",
        8080,
        lci,
        "project-a",
        "isolated-db",
        run_id=kwargs["run_id"],
        request_id="request-two",
        preflight_id=preflight2["preflight_id"],
        operation_id=first["operation_id"],
        operation_dir=kwargs["operation_dir"],
        client=client,
    )
    assert resumed["status"] == "success"
    assert resumed["execution_mode"] == "resumed"
    plan = {entry["id"]: entry for entry in resumed["entity_plan"]}
    assert plan[FLOW_ID]["status"] == "done"
    assert plan[PROCESS_ID]["status"] == "done"
    assert plan[PRODUCT_SYSTEM_ID]["status"] == "done"
    assert resumed.get("changed_entities")


def test_resume_scope_mismatch_message(lock_root, tmp_path):
    client = FakeImportClient()
    lci, kwargs = _start_import(tmp_path, client)
    first = operations.import_request(
        "localhost", 8080, lci, "project-a", "isolated-db", **kwargs
    )
    preflight2 = operations.preflight(
        "localhost",
        8080,
        lci,
        "other-category",
        "isolated-db",
        run_id=kwargs["run_id"],
        operation_dir=kwargs["operation_dir"],
        client=client,
    )
    result = operations.resume_import_request(
        "localhost",
        8080,
        lci,
        "other-category",
        "isolated-db",
        run_id=kwargs["run_id"],
        request_id="request-two",
        preflight_id=preflight2["preflight_id"],
        operation_id=first["operation_id"],
        operation_dir=kwargs["operation_dir"],
        client=client,
    )
    assert result["status"] == "rejected"
    assert any("resume_scope_mismatch" in err for err in result["errors"])
    assert any("field=category" in err for err in result["errors"])


def test_cleanup_deletes_only_in_category_uuid_targets(tmp_path):
    from harness.tools.shared.control_openlca import cleanup

    class LookupClient:
        def get(self, *_a, **_k):
            raise AssertionError("cleanup must not call full data/get")

        def get_descriptor(self, model_type, entity_id):
            if entity_id == "process-1":
                return olca_schema.Process(
                    id="process-1", name="In", category="project-a"
                )
            if entity_id == "process-2":
                return olca_schema.Process(
                    id="process-2", name="Out", category="project-b"
                )
            return None

        def get_descriptors(self, model_type):
            return []

        def delete(self, reference):
            self.deleted = reference

    client = LookupClient()
    resolved, skipped = cleanup._resolve_uuid_targets(
        client,
        "project-a",
        [("Process", "process-1"), ("Process", "process-2")],
    )
    assert len(resolved) == 1
    assert resolved[0][1].id == "process-1"
    assert skipped and skipped[0]["id"] == "process-2"
