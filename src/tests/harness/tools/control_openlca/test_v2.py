from __future__ import annotations

import json
import multiprocessing
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import olca_schema as s
import pytest
import requests

from harness.tools.control_openlca.utils import guard, operations, readonly
from harness.tools.lca_artifacts import checks, report
from harness.tools.lca_artifacts.store import MAX_RESPONSE_BYTES, Context, invoke
from tests.support.openlca_fakes import (
    FakeClient,
    FakeImportClient,
    write_flow,
    write_product_system_fixture,
)


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.setenv("LCA_IPC_LOCK_ROOT", str(tmp_path / "locks"))
    ctx = Context(
        tmp_path,
        tmp_path / "workspace",
        "run-one",
        "04-openlca-reporting",
        1,
        metadata={"lca": {"phase": "report"}},
    )
    return ctx


def start_import(ctx, client) -> tuple[Path, dict[str, Any]]:
    lci = ctx.workspace / "outputs" / "LCI"
    write_flow(lci)
    operation_dir = ctx.workspace / "memory" / "import-operations"
    preflight = operations.preflight(
        "localhost",
        8080,
        lci,
        "project-a",
        "isolated-db",
        run_id=ctx.run_id,
        operation_dir=operation_dir,
        client=client,
    )
    assert preflight["ok"]
    kwargs: dict[str, Any] = {
        "run_id": ctx.run_id,
        "request_id": "request-one",
        "preflight_id": preflight["preflight_id"],
        "operation_dir": operation_dir,
        "client": client,
    }
    return lci, kwargs


def test_request_reuse_and_changed_identity(context):
    client = FakeImportClient()
    lci, kwargs = start_import(context, client)
    first = operations.import_request(
        "localhost", 8080, lci, "project-a", "isolated-db", **kwargs
    )
    assert first["status"] == "success"
    count = len(client.put_calls)
    again = operations.import_request(
        "localhost", 8080, lci, "project-a", "isolated-db", **kwargs
    )
    assert again["execution_mode"] == "reused"
    assert again["operation_id"] == first["operation_id"]
    assert len(client.put_calls) == count
    write_flow(lci, name="Changed flow")
    wrong = operations.import_request(
        "localhost", 8080, lci, "project-a", "isolated-db", **kwargs
    )
    assert wrong["status"] == "rejected"
    assert len(client.put_calls) == count
    preflight = operations.preflight(
        "localhost",
        8080,
        lci,
        "project-a",
        "isolated-db",
        run_id=context.run_id,
        operation_dir=kwargs["operation_dir"],
        client=client,
    )
    kwargs.update(request_id="new-request", preflight_id=preflight["preflight_id"])
    new = operations.import_request(
        "localhost", 8080, lci, "project-a", "isolated-db", **kwargs
    )
    assert new["status"] == "success"
    assert new["operation_id"] != first["operation_id"]


def test_stale_preflight_and_consumption(context):
    client = FakeImportClient()
    lci, kwargs = start_import(context, client)
    write_flow(lci, name="changed before import")
    result = operations.import_request(
        "localhost", 8080, lci, "project-a", "isolated-db", **kwargs
    )
    assert result["status"] == "rejected"
    assert not client.put_calls


def test_failed_import_never_retries(context):
    client = FakeImportClient()
    client.put_error = requests.Timeout("read timed out")
    lci, kwargs = start_import(context, client)
    first = operations.import_request(
        "localhost", 8080, lci, "project-a", "isolated-db", **kwargs
    )
    assert first["status"] == "partial_failure"
    with patch.object(guard, "probe_ipc", return_value=client):
        again = operations.import_request(
            "localhost", 8080, lci, "project-a", "isolated-db", **kwargs
        )
    assert again["execution_mode"] == "reused"
    assert len(client.put_calls) == 1
    # Status query never needs the endpoint lock or a live connection.
    with patch.object(guard, "probe_ipc", side_effect=AssertionError("IPC forbidden")):
        value = operations.get_operation(
            kwargs["operation_dir"], run_id=context.run_id, request_id="request-one"
        )
    assert value["operation_id"] == first["operation_id"]


def _hold_lock(path, ready):
    with guard.file_lock(Path(path)):
        ready.set()
        time.sleep(0.5)


def test_cross_process_lock(tmp_path):
    mp = multiprocessing.get_context("spawn")
    ready = mp.Event()
    path = tmp_path / "shared.lock"
    process = mp.Process(target=_hold_lock, args=(str(path), ready))
    process.start()
    try:
        assert ready.wait(10)
        with pytest.raises(guard.EndpointBusy):
            with guard.file_lock(path, timeout=0.1):
                pytest.fail("overlapping IPC owners")
    finally:
        process.join(10)
        if process.is_alive():
            process.terminate()
            process.join()
    assert process.exitcode == 0
    with guard.file_lock(path, timeout=0.1):
        pass


def test_large_result_bounded_and_artifact_failure(context):
    raw = {
        "ok": True,
        "background_provider_checks": [
            {"output_flow_ids": [str(i) * 30 for i in range(50000)]}
        ],
    }
    value = invoke("preflight_import_lci", lambda: raw, ctx=context)
    assert len(json.dumps(value, ensure_ascii=False).encode()) <= MAX_RESPONSE_BYTES
    saved = json.loads(context.resolve_ref(value["artifacts"][0]).read_text())
    assert saved == raw
    with patch.object(Context, "save_result", side_effect=OSError("disk full")):
        failed = invoke("get_model_graph", lambda: raw, ctx=context)
    assert failed["status"] == "failed"
    assert failed["artifacts"] == []
    assert failed["errors"][0]["kind"] == "artifact_io"


def test_batch_reads_once(context):
    proc = s.Process(
        id="p",
        name="provider",
        exchanges=[s.Exchange(flow=s.Ref(id="f"), is_input=False)],
    )
    client = FakeClient(
        [s.Ref(id="p", name="electricity market")], entities={(s.Process, "p"): proc}
    )
    with (
        patch.object(readonly, "create_ipc_client", return_value=client),
        patch.object(client, "get_descriptors", wraps=client.get_descriptors) as read,
    ):
        result = readonly.query_descriptors_batch(
            "localhost", 8080, "Process", ["market", "electricity"]
        )
        assert len(result["queries"]) == 2
        assert read.call_count == 1
    with (
        patch.object(readonly, "create_ipc_client", return_value=client),
        patch.object(client, "get", wraps=client.get) as read,
    ):
        value = readonly.validate_providers_batch(
            "localhost", 8080, [{"process_id": "p", "flow_id": "f"}] * 8
        )
        assert value["ok"]
        assert read.call_count == 1


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def seed_passed_mapping_check(ctx):
    inputs = checks.dependencies(ctx, "mapping")
    path = checks.check_path(ctx, "mapping")
    write_json(
        path,
        {
            "check_id": "mapping",
            "checker_version": checks.CHECKER_VERSION,
            "status": "passed",
            "inputs": inputs,
            "executed_at": "2020-01-01T00:00:00Z",
            "summary": "mapping: 0 issue(s)",
            "errors": [],
            "warnings": [],
            "stage": ctx.stage,
            "assignment": ctx.assignment,
            "attempt": ctx.attempt,
        },
    )


def seed_report(ctx):
    out = ctx.workspace / "outputs"
    write_json(
        out / "inventory" / "extracted-bom.json",
        {
            "items": [
                {
                    "item_id": "b1",
                    "name": "材料",
                    "quantity": 1,
                    "unit": "kg",
                    "source_locations": ["harness/knowledge/source.md#L1"],
                }
            ]
        },
    )
    write_json(
        out / "inventory" / "process-mapping.json",
        {"items": [{"item_id": "b1", "selection_reason": "同功能"}]},
    )
    write_json(out / "LCI" / "product_systems" / "s.json", {"@id": "system-one"})
    write_json(
        checks.calculation_path(ctx),
        {
            "calculations": [
                {"product_system": "system-one", "impact_method": "method-one"}
            ]
        },
    )
    mapping_ctx = Context(
        ctx.project,
        ctx.workspace,
        ctx.run_id,
        "03-dataset-mapping",
        1,
        "reviewer",
        metadata={"lca": {"phase": "mapping"}},
    )
    mapping_ctx.manifest.parent.mkdir(parents=True, exist_ok=True)
    if not mapping_ctx.manifest.is_file():
        mapping_ctx.manifest.write_text(
            json.dumps({"accepted": {}, "run_id": ctx.run_id, "calls": []}),
            encoding="utf-8",
        )
    seed_passed_mapping_check(mapping_ctx)
    checks.record_acceptance(mapping_ctx)
    ctx.save_result(
        "import_lci",
        {
            "status": "success",
            "operation_id": "op-one",
            "request_id": "request-one",
            "identity": {"run_id": ctx.run_id},
            "success_count": 1,
            "failed_count": 0,
        },
        {},
    )
    ctx.save_result(
        "get_model_graph",
        {
            "status": "success",
            "product_system": {"id": "system-one"},
            "nodes": [{"id": "p"}],
            "broken_links": [],
        },
        {"product_system": "system-one"},
    )
    ctx.save_result(
        "calculate_product_system",
        {
            "status": "success",
            "product_system": {"id": "system-one"},
            "impact_method": {"id": "method-one"},
            "calculation_setup": {"amount": 1.0},
            "resource_released": True,
            "impact_categories": [{"name": "climate", "amount": 2.5, "unit": "kg"}],
        },
        {"product_system": "system-one", "impact_method": "method-one"},
    )
    text = "# 中文报告\n\n" + "\n".join(
        "\n".join(report.markers(n)) for n in ("inventory", "mapping", "lcia")
    )
    (out / "reports" / "lca_report.md").write_text(text, encoding="utf-8")
    report.render(ctx)


def test_report_only_reuses_without_ipc_and_checks_tampering(context):
    seed_report(context)
    assert checks.validate(context, "report")["ok"]
    retry = Context(
        context.project,
        context.workspace,
        context.run_id,
        context.stage,
        2,
        metadata=dict(context.metadata),
    )
    path = context.workspace / "outputs" / "reports" / "lca_report.md"
    path.write_text(
        path.read_text().replace("中文报告", "修改后的中文说明"), encoding="utf-8"
    )
    with patch(
        "harness.tools.control_openlca.utils.connection.create_ipc_client",
        side_effect=AssertionError("no IPC"),
    ):
        assert checks.validation_state(retry, "report")["status"] == "stale"
        assert checks.reuse_status(retry)["rework_scope"] == "report_only"
        report.render(retry)
        assert checks.validate(retry, "report")["ok"]
    path.write_text(path.read_text().replace("2.5", "999"))
    assert not checks.validate(retry, "report")["ok"]
    new_run = Context(
        context.project,
        context.workspace,
        "new-run",
        context.stage,
        2,
        metadata=dict(context.metadata),
    )
    assert checks.validation_state(new_run, "report")["status"] == "not_run"
    assert not checks.reuse_status(new_run)["eligible"]


def test_upstream_raw_and_checker_invalidation(context, monkeypatch):
    seed_report(context)
    checks.validate(context, "report")
    monkeypatch.setattr(checks, "CHECKER_VERSION", "next")
    assert checks.validation_state(context, "report")["status"] == "stale"
    path = context.workspace / "outputs" / "inventory" / "process-mapping.json"
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="stale"):
        checks.require_approved_model(context)
    retry = Context(
        context.project,
        context.workspace,
        context.run_id,
        context.stage,
        2,
        metadata=dict(context.metadata),
    )
    assert checks.reuse_status(retry)["rework_scope"] == "model_changed"


def test_reviewer_and_path_guards(context):
    seed_report(context)
    reviewer = Context(
        context.project,
        context.workspace,
        context.run_id,
        context.stage,
        1,
        "reviewer",
        metadata=dict(context.metadata),
    )
    assert checks.validate(reviewer, "report")["ok"]
    with pytest.raises(ValueError, match="reviewer"):
        report.render(reviewer)
    with pytest.raises(ValueError, match="escapes"):
        context.resolve_ref({"path": "../../outside", "sha256": "x"})
    with pytest.raises(ValueError, match="differs from"):
        checks.require_import_directory(
            context, context.workspace / "tmp" / "unchecked-LCI"
        )


def test_error_after_success_invalidates_reuse(context):
    seed_report(context)
    invoke(
        "calculate_product_system",
        lambda: (_ for _ in ()).throw(requests.Timeout("timed out")),
        arguments={"product_system": "system-one", "impact_method": "method-one"},
        ctx=context,
    )
    retry = Context(
        context.project,
        context.workspace,
        context.run_id,
        context.stage,
        2,
        metadata=dict(context.metadata),
    )
    assert not checks.reuse_status(retry)["eligible"]


def test_calculation_change_and_raw_corruption(context):
    seed_report(context)
    retry = Context(
        context.project,
        context.workspace,
        context.run_id,
        context.stage,
        2,
        metadata=dict(context.metadata),
    )
    write_json(
        checks.calculation_path(context),
        {
            "calculations": [
                {
                    "product_system": "system-one",
                    "impact_method": "method-one",
                    "amount": 2.0,
                }
            ]
        },
    )
    assert checks.reuse_status(retry)["rework_scope"] == "calculation_changed"
    assert not checks.reuse_status(retry)["eligible"]
    with pytest.raises(ValueError, match="differs from plan"):
        checks.require_calculation_plan(
            retry, {"product_system": "system-one", "impact_method": "method-one"}
        )
    write_json(
        checks.calculation_path(context),
        {
            "calculations": [
                {"product_system": "system-one", "impact_method": "method-one"}
            ]
        },
    )
    raw = context.resolve_ref(context.load_manifest()["calls"][0]["artifact"])
    raw.write_text('{"status":"success","forged":true}')
    assert not checks.reuse_status(retry)["eligible"]
    assert not checks.validate(retry, "report")["ok"]


def test_ignored_source_manifest_and_inventory_dependency_scope(context):
    from harness.tools.control_openlca.utils.workflow import sha256_file
    from harness.tools.lca_artifacts.store import discover_sources

    source = context.project / "harness" / "knowledge" / "ignored.md"
    source.parent.mkdir(parents=True)
    source.write_text("source")
    (context.project / ".gitignore").write_text("harness/knowledge/*\nworkspace/*\n")
    assert discover_sources(context.project)["count"] == 1
    inventory = Context(
        context.project,
        context.workspace,
        context.run_id,
        "02-inventory-extraction",
        1,
        assignment="02-inventory-extraction.executor",
        metadata={"lca": {"phase": "inventory"}},
    )
    manifest_path = inventory.sources_manifest_path()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        manifest_path,
        {
            "assignment": inventory.assignment,
            "count": 1,
            "files": [
                {
                    "path": "harness/knowledge/ignored.md",
                    "sha256": sha256_file(source),
                    "readable": True,
                }
            ],
        },
    )
    bom = context.workspace / "outputs" / "inventory" / "extracted-bom.json"
    row = {
        "item_id": "one",
        "name": "物料",
        "quantity": 1,
        "unit": "kg",
        "process": "制造",
        "transport": None,
        "geography": "CN",
        "source_locations": ["harness/knowledge/ignored.md#L1"],
        "extraction_status": "extracted",
    }
    write_json(bom, {"items": [row]})
    assert checks.validate(inventory, "inventory")["ok"]
    write_json(bom.parent / "process-mapping.json", {"items": []})
    assert checks.validation_state(inventory, "inventory")["status"] == "passed"
    source.write_text("changed")
    assert checks.validation_state(inventory, "inventory")["status"] == "stale"
    write_json(bom, {"items": [row, row]})
    assert not checks.validate(inventory, "inventory")["ok"]


def test_busy_unknown_probe_and_recovery(context):
    with pytest.raises(requests.Timeout):
        with guard.endpoint_guard("localhost", 8080):
            raise requests.Timeout("timed out")
    with patch.object(guard, "probe_ipc", side_effect=requests.Timeout("still busy")):
        with pytest.raises(guard.EndpointBusy):
            with guard.endpoint_guard("localhost", 8080):
                pytest.fail("must not run while endpoint is uncertain")
    with patch.object(guard, "probe_ipc", return_value=FakeClient()) as probe:
        with guard.endpoint_guard("localhost", 8080):
            pass
    assert probe.call_count == 1


def test_preflight_is_single_use_and_cross_run_not_reused(context):
    client = FakeImportClient()
    lci, kwargs = start_import(context, client)
    first = operations.import_request(
        "localhost", 8080, lci, "project-a", "isolated-db", **kwargs
    )
    kwargs["request_id"] = "another-request"
    repeated = operations.import_request(
        "localhost", 8080, lci, "project-a", "isolated-db", **kwargs
    )
    assert repeated["status"] == "rejected"
    assert len(client.put_calls) == 1
    assert (
        operations.get_operation(
            kwargs["operation_dir"],
            run_id="different-run",
            operation_id=first["operation_id"],
        )["status"]
        == "not_found"
    )


def test_mcp_reviewer_cannot_write_or_calculate(context, monkeypatch):
    from harness.tools.control_openlca import main

    monkeypatch.setenv("LCA_RUN_ID", context.run_id)
    monkeypatch.setenv("LCA_WORKSPACE", str(context.workspace))
    monkeypatch.setenv("LCA_ROLE", "reviewer")
    with patch.object(
        main,
        "run_calculate_product_system",
        side_effect=AssertionError("must not call"),
    ):
        value = main.calculate_product_system("system", "method")
    assert value["status"] == "failed"
    assert "reviewer" in value["errors"][0]["message"]


def test_clean_reconciles_active_pointer_without_rewriting_old_receipt(context):
    client = FakeImportClient()
    client.fail_put = True
    lci, kwargs = start_import(context, client)
    first = operations.import_request(
        "localhost", 8080, lci, "project-a", "isolated-db", **kwargs
    )
    assert first["status"] == "partial_failure"
    operations.reconcile_cleanup(
        kwargs["operation_dir"], "localhost", 8080, "project-a"
    )
    assert not (kwargs["operation_dir"] / "current.json").exists()
    assert (
        operations.get_operation(
            kwargs["operation_dir"], run_id=context.run_id, request_id="request-one"
        )["status"]
        == "partial_failure"
    )


def test_mapping_checks_coverage_and_lci_semantics(context):
    mapping_ctx = Context(
        context.project,
        context.workspace,
        context.run_id,
        "03-dataset-mapping",
        1,
        metadata={"lca": {"phase": "mapping"}},
    )
    root = context.workspace / "outputs"
    write_product_system_fixture(root / "LCI")
    (root / "LCI" / "human_readable_mapping.md").write_text("映射说明")
    write_json(
        root / "inventory" / "extracted-bom.json", {"items": [{"item_id": "b1"}]}
    )
    write_json(
        root / "inventory" / "process-mapping.json", {"items": [{"item_id": "b1"}]}
    )
    assert checks.validate(mapping_ctx, "mapping")["ok"]
    write_json(
        root / "inventory" / "process-mapping.json", {"items": [{"item_id": "missing"}]}
    )
    assert not checks.validate(mapping_ctx, "mapping")["ok"]


def test_raw_pointer_read_uses_checksum(context, monkeypatch):
    from harness.tools.lca_artifacts import main

    monkeypatch.setenv("LCA_WORKSPACE", str(context.workspace))
    ref, _ = context.save_result("example", {"queries": [{"count": 31}]}, {})
    result = main.read_artifact(
        ref["path"], ref["sha256"], json_pointer="/queries/0/count"
    )
    assert result["items"] == [{"text": "31"}]
    broken = main.read_artifact(ref["path"], "wrong", json_pointer="/queries/0/count")
    assert broken["status"] == "failed"


def test_request_deadline_reserves_disposal(context):
    with guard.endpoint_guard("localhost", 8080):
        guard._local.deadline = time.monotonic() - 1
        with pytest.raises(requests.Timeout):
            guard.remaining_budget()
        with guard.cleanup_budget():
            budget = guard.remaining_budget()
            assert budget is not None
            assert 0 < budget <= 10
        with pytest.raises(requests.Timeout):
            guard.remaining_budget()


def test_entity_transport_error_never_triggers_fallback_scan(context):
    from harness.tools.control_openlca.utils.entity import find_entity

    client = FakeClient(error=requests.Timeout("timed out"))
    with patch.object(client, "get_descriptors", wraps=client.get_descriptors) as scan:
        with pytest.raises(requests.Timeout):
            find_entity(client, s.Process, "unresolved-name")
    assert scan.call_count == 0


def test_rpc_failure_is_not_an_empty_descriptor_list(context):
    import olca_ipc

    from harness.tools.control_openlca.utils.connection import (
        BoundedIPCClient,
        OpenLCARequestError,
        long_read_sec,
        mcp_tool_timeout_sec,
        reload_ipc_timeout_settings,
        session_budget_sec,
    )

    client = BoundedIPCClient("http://localhost:8080")
    try:
        with patch.object(
            olca_ipc.Client, "rpc_call", return_value=(None, "database busy")
        ):
            with pytest.raises(OpenLCARequestError, match="database busy"):
                client.get_descriptors(s.Process)
    finally:
        client.close()

    assert session_budget_sec(long_running=True) >= long_read_sec() + 1
    assert mcp_tool_timeout_sec() >= int(session_budget_sec(long_running=True) + 120)
    with patch.dict(
        "os.environ",
        {
            "OPENLCA_IPC_LONG_READ_SEC": "900",
            "OPENLCA_IPC_SESSION_BUDGET_SEC": "8000",
        },
        clear=False,
    ):
        reload_ipc_timeout_settings()
        assert long_read_sec() == 900
        assert session_budget_sec(long_running=True) == 8000
    reload_ipc_timeout_settings()


def test_mcp_channel_gate_rejects_without_env(monkeypatch):
    from harness.tools.control_openlca import main

    monkeypatch.delenv("LCA_CONTROL_OPENLCA_MCP", raising=False)
    blocked = main.health_check()
    assert blocked["status"] == "failed"
    assert "MCP" in blocked["errors"][0]["message"]


def test_resolve_ipc_tool_timeout_sec_clamps(monkeypatch):
    from harness.tools.control_openlca.utils.connection import (
        IPC_TOOL_TIMEOUT_MAX_SEC,
        IPC_TOOL_TIMEOUT_MIN_SEC,
        long_read_sec,
        resolve_ipc_tool_timeout_sec,
    )

    default = resolve_ipc_tool_timeout_sec(None)
    assert default >= IPC_TOOL_TIMEOUT_MIN_SEC
    floor = max(IPC_TOOL_TIMEOUT_MIN_SEC, long_read_sec() + 1.0)
    assert resolve_ipc_tool_timeout_sec(100) == floor
    assert resolve_ipc_tool_timeout_sec(99999) == IPC_TOOL_TIMEOUT_MAX_SEC
    assert resolve_ipc_tool_timeout_sec(3600) == 3600.0


def test_long_tool_reports_applied_timeout_sec(context, monkeypatch):
    from harness.tools.control_openlca import main
    from harness.tools.control_openlca.utils import guard

    monkeypatch.setenv("LCA_RUN_ID", context.run_id)
    monkeypatch.setenv("LCA_WORKSPACE", str(context.workspace))
    monkeypatch.setenv("LCA_STAGE", context.stage)
    monkeypatch.setenv("LCA_ATTEMPT", str(context.attempt))
    with (
        patch.object(
            guard,
            "serialized_ipc",
            side_effect=lambda fn, **kwargs: fn("127.0.0.1", 8080),
        ),
        patch.object(main, "run_get_model_graph", return_value={"ok": True}),
    ):
        result = main.get_model_graph("product-system-id", timeout_sec=3600)
    assert result["status"] == "success"
    assert result["applied_timeout_sec"] == 3600


def test_session_request_timeout_follows_remaining_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("LCA_IPC_LOCK_ROOT", str(tmp_path / "locks"))
    from harness.tools.control_openlca.utils.connection import (
        LONG_REQUEST_TIMEOUT,
        session_request_timeout,
    )

    assert session_request_timeout() == LONG_REQUEST_TIMEOUT
    with guard.endpoint_guard("localhost", 8080, budget_sec=3600):
        timeout = session_request_timeout()
    assert timeout[0] == 2.0
    assert 3500 < timeout[1] <= 3600


def test_create_ipc_client_defaults_to_session_timeout(tmp_path, monkeypatch):
    monkeypatch.setenv("LCA_IPC_LOCK_ROOT", str(tmp_path / "locks"))
    from harness.tools.control_openlca.utils.connection import (
        LONG_REQUEST_TIMEOUT,
        create_ipc_client,
    )

    dummy = FakeClient()
    with patch(
        "harness.tools.control_openlca.utils.connection.BoundedIPCClient",
        return_value=dummy,
    ) as factory:
        create_ipc_client("localhost", 8080)
    factory.assert_called_once_with(
        "http://localhost:8080",
        timeout=LONG_REQUEST_TIMEOUT,
    )

    with guard.endpoint_guard("localhost", 8080, budget_sec=3600):
        with patch(
            "harness.tools.control_openlca.utils.connection.BoundedIPCClient",
            return_value=dummy,
        ) as factory:
            create_ipc_client("localhost", 8080)
        timeout = factory.call_args.kwargs["timeout"]
    assert timeout[0] == 2.0
    assert 3500 < timeout[1] <= 3600


def test_query_descriptors_reports_applied_timeout_sec(context, monkeypatch):
    from harness.tools.control_openlca import main
    from harness.tools.control_openlca.utils import guard

    monkeypatch.setenv("LCA_RUN_ID", context.run_id)
    monkeypatch.setenv("LCA_WORKSPACE", str(context.workspace))
    monkeypatch.setenv("LCA_STAGE", context.stage)
    monkeypatch.setenv("LCA_ATTEMPT", str(context.attempt))
    with (
        patch.object(
            guard,
            "serialized_ipc",
            side_effect=lambda fn, **kwargs: fn("127.0.0.1", 8080),
        ),
        patch.object(main, "run_query_descriptors", return_value={"ok": True}),
    ):
        result = main.query_descriptors("Process", timeout_sec=3600)
    assert result["status"] == "success"
    assert result["applied_timeout_sec"] == 3600
