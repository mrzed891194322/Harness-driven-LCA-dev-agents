from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import olca_schema

from harness.tools.control_openlca import main as mcp_module
from harness.tools.control_openlca.utils import connection
from harness.tools.control_openlca.utils import readonly


class FakeClient:
    def __init__(
        self,
        descriptors: list[object] | None = None,
        error: Exception | None = None,
        *,
        entities: dict[tuple[type, str], object] | None = None,
        providers: list[object] | None = None,
    ) -> None:
        self.descriptors = descriptors or []
        self.error = error
        self.entities = entities or {}
        self.providers = providers or []
        self.requested_type: type | None = None
        self.closed = False

    def rpc_call(self, method: str, params: dict[str, str]) -> tuple[list, str | None]:
        self.requested_type = getattr(olca_schema, params["@type"])
        if self.error is not None:
            raise self.error
        return [], None

    def close(self) -> None:
        self.closed = True

    def get_descriptors(self, model_type: type) -> list[object]:
        self.requested_type = model_type
        if self.error is not None:
            raise self.error
        return self.descriptors

    def get(self, model_type: type, entity_id: str) -> object | None:
        if self.error is not None:
            raise self.error
        return self.entities.get((model_type, entity_id))

    def get_providers(self, flow: object) -> list[object]:
        if self.error is not None:
            raise self.error
        return self.providers


class ReadOnlyServiceTests(unittest.TestCase):
    def test_build_endpoint_validates_and_formats_hosts(self) -> None:
        self.assertEqual(connection.build_endpoint("localhost", 8080), "http://localhost:8080")
        self.assertEqual(connection.build_endpoint("::1", 8080), "http://[::1]:8080")
        with self.assertRaisesRegex(ValueError, "not a URL"):
            connection.build_endpoint("http://localhost", 8080)
        with self.assertRaisesRegex(ValueError, "between 1 and 65535"):
            connection.build_endpoint("localhost", 0)

    def test_timeout_adapter_replaces_requests_default_none(self) -> None:
        adapter = connection._TimeoutHTTPAdapter((1.0, 3.0))
        with patch.object(
            connection.HTTPAdapter,
            "send",
            return_value=object(),
        ) as send:
            adapter.send(object(), timeout=None)

        self.assertEqual(send.call_args.kwargs["timeout"], (1.0, 3.0))

    def test_product_system_creation_returns_valid_reference(self) -> None:
        client = connection.BoundedIPCClient("http://localhost:8080")
        process = olca_schema.Ref(id="process-id", name="Reference process")
        config = olca_schema.LinkingConfig(
            prefer_unit_processes=False,
            provider_linking=olca_schema.ProviderLinking.PREFER_DEFAULTS,
        )
        try:
            with patch.object(
                client,
                "rpc_call",
                return_value=(
                    {
                        "@type": "ProductSystem",
                        "@id": "product-system-id",
                        "name": "Generated system",
                    },
                    None,
                ),
            ) as rpc_call:
                result = client.create_product_system(process, config)
        finally:
            client.close()

        self.assertEqual(result.id, "product-system-id")
        rpc_call.assert_called_once_with(
            "data/create/system",
            {
                "process": {"@id": "process-id", "name": "Reference process"},
                "config": {
                    "preferUnitProcesses": False,
                    "providerLinking": "PREFER_DEFAULTS",
                },
            },
        )

    def test_product_system_creation_preserves_rpc_error(self) -> None:
        client = connection.BoundedIPCClient("http://localhost:8080")
        try:
            with (
                patch.object(
                    client,
                    "rpc_call",
                    return_value=(
                        None,
                        "reference process has no quantitative reference",
                    ),
                ),
                self.assertRaisesRegex(
                    connection.OpenLCARequestError,
                    "reference process has no quantitative reference",
                ),
            ):
                client.create_product_system(
                    olca_schema.Ref(id="process-id"),
                )
        finally:
            client.close()

    def test_product_system_creation_rejects_invalid_response(self) -> None:
        responses = (
            None,
            {"@type": "ProductSystem", "name": "Missing UUID"},
            {"@type": "ProductSystem", "@id": 42},
        )
        for response in responses:
            with self.subTest(response=response):
                client = connection.BoundedIPCClient("http://localhost:8080")
                try:
                    with (
                        patch.object(
                            client,
                            "rpc_call",
                            return_value=(response, None),
                        ),
                        self.assertRaises(connection.OpenLCARequestError),
                    ):
                        client.create_product_system(
                            olca_schema.Ref(id="process-id"),
                        )
                finally:
                    client.close()

    def test_probe_ipc_reuses_client_and_resolves_model_name(self) -> None:
        client = FakeClient()
        with patch.object(
            connection,
            "BoundedIPCClient",
            return_value=client,
        ) as client_factory:
            result = connection.probe_ipc("localhost", 8080, "Process")

        self.assertIs(result, client)
        self.assertIs(client.requested_type, olca_schema.Process)
        client_factory.assert_called_once_with(
            "http://localhost:8080",
            timeout=connection.HEALTH_REQUEST_TIMEOUT,
        )

    def test_health_check_returns_success(self) -> None:
        client = FakeClient()
        with patch.object(readonly, "probe_ipc", return_value=client) as probe:
            result = readonly.health_check("127.0.0.1", 8080)

        self.assertTrue(result["ok"])
        self.assertEqual(result["endpoint"], "http://127.0.0.1:8080")
        self.assertEqual(result["attempt_count"], 1)
        self.assertTrue(client.closed)
        probe.assert_called_once_with(
            "127.0.0.1",
            8080,
            olca_schema.Currency,
            timeout=connection.HEALTH_REQUEST_TIMEOUT,
        )

    def test_health_check_returns_diagnostics_on_connection_failure(self) -> None:
        with (
            patch.object(
                readonly,
                "probe_ipc",
                side_effect=OSError("connection refused"),
            ) as probe,
            patch.object(readonly.time, "sleep") as sleep,
        ):
            result = readonly.health_check("127.0.0.1", 8080)

        self.assertFalse(result["ok"])
        self.assertEqual(result["attempt_count"], 4)
        self.assertEqual(result["reconnect_count"], 3)
        self.assertEqual(result["error_type"], "OSError")
        self.assertIn("connection refused", result["error"])
        self.assertEqual(len(result["diagnostics"]), 3)
        self.assertEqual(probe.call_count, 4)
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            [0.25, 0.5, 1.0],
        )

    def test_health_check_succeeds_on_fourth_attempt(self) -> None:
        client = FakeClient()
        with (
            patch.object(
                readonly,
                "probe_ipc",
                side_effect=[
                    OSError("first"),
                    OSError("second"),
                    OSError("third"),
                    client,
                ],
            ),
            patch.object(readonly.time, "sleep"),
        ):
            result = readonly.health_check("127.0.0.1", 8080)

        self.assertTrue(result["ok"])
        self.assertEqual(result["attempt_count"], 4)
        self.assertEqual(result["reconnect_count"], 3)
        self.assertTrue(client.closed)

    def test_legacy_cli_connection_reconnects_three_times(self) -> None:
        probe_client = FakeClient()
        operation_client = FakeClient()
        with (
            patch.object(
                connection,
                "probe_ipc",
                side_effect=[
                    OSError("first"),
                    OSError("second"),
                    OSError("third"),
                    probe_client,
                ],
            ) as probe,
            patch.object(
                connection,
                "create_ipc_client",
                return_value=operation_client,
            ) as create,
            patch.object(connection.time, "sleep") as sleep,
        ):
            result = connection.connect_ipc(
                "127.0.0.1",
                8080,
                olca_schema.Process,
            )

        self.assertIs(result, operation_client)
        self.assertTrue(probe_client.closed)
        self.assertEqual(probe.call_count, 4)
        create.assert_called_once_with("127.0.0.1", 8080)
        self.assertEqual(sleep.call_count, 3)

    def test_query_filters_case_insensitively_and_paginates(self) -> None:
        client = FakeClient([
            SimpleNamespace(
                id="flow-1",
                name="Electricity, medium voltage",
                description="first",
                category="energy",
                ref_unit="kWh",
            ),
            SimpleNamespace(
                id="flow-2",
                name="electricity, low voltage",
                description="second",
                category="energy",
                ref_unit="kWh",
            ),
            SimpleNamespace(id="flow-3", name="Natural gas"),
        ])
        with patch.object(readonly, "create_ipc_client", return_value=client):
            result = readonly.query_descriptors(
                "localhost",
                8080,
                "Flow",
                search=" ELECTRICITY ",
                limit=1,
                offset=1,
            )

        self.assertIs(client.requested_type, olca_schema.Flow)
        self.assertEqual(result["total_descriptors"], 3)
        self.assertEqual(result["total_matches"], 2)
        self.assertEqual(result["returned"], 1)
        self.assertFalse(result["has_more"])
        self.assertIsNone(result["next_offset"])
        self.assertEqual(result["items"][0]["id"], "flow-2")
        self.assertEqual(result["items"][0]["ref_unit"], "kWh")

    def test_query_reports_next_offset(self) -> None:
        client = FakeClient([
            SimpleNamespace(id="process-1", name="A"),
            SimpleNamespace(id="process-2", name="B"),
        ])
        with patch.object(readonly, "create_ipc_client", return_value=client):
            result = readonly.query_descriptors(
                "localhost",
                8080,
                "Process",
                limit=1,
            )

        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 1)

    def test_query_validates_type_and_pagination(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported entity_type"):
            readonly.query_descriptors("localhost", 8080, "Database")
        with self.assertRaisesRegex(ValueError, "between 1 and 200"):
            readonly.query_descriptors("localhost", 8080, "Flow", limit=201)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            readonly.query_descriptors("localhost", 8080, "Flow", offset=-1)

    def test_query_wraps_ipc_errors_with_endpoint_context(self) -> None:
        client = FakeClient(error=OSError("connection refused"))
        with (
            patch.object(readonly, "create_ipc_client", return_value=client),
            self.assertRaisesRegex(RuntimeError, "http://localhost:8080"),
        ):
            readonly.query_descriptors("localhost", 8080, "Flow")

    def test_flow_providers_filter_and_paginate_compact_references(self) -> None:
        flow_id = "flow-1"
        flow = olca_schema.Flow(id=flow_id, name="Electricity")
        providers = [
            olca_schema.TechFlow(
                provider=olca_schema.Ref(
                    id="provider-2",
                    name="Electricity market B",
                    category="energy",
                    location="DE",
                ),
                flow=olca_schema.Ref(
                    id=flow_id,
                    name="Electricity",
                    ref_unit="kWh",
                ),
            ),
            olca_schema.TechFlow(
                provider=olca_schema.Ref(
                    id="provider-1",
                    name="Electricity market A",
                    category="energy",
                    location="DE",
                ),
                flow=olca_schema.Ref(
                    id=flow_id,
                    name="Electricity",
                    ref_unit="kWh",
                ),
            ),
            olca_schema.TechFlow(
                provider=olca_schema.Ref(
                    id="provider-3",
                    name="Electricity market C",
                    category="energy",
                    location="FR",
                ),
                flow=olca_schema.Ref(id=flow_id, name="Electricity"),
            ),
        ]
        client = FakeClient(
            entities={(olca_schema.Flow, flow_id): flow},
            providers=providers,
        )
        with patch.object(readonly, "create_ipc_client", return_value=client):
            result = readonly.get_flow_providers(
                "localhost",
                8080,
                flow_id,
                location="de",
                limit=1,
            )

        self.assertTrue(result["flow_found"])
        self.assertEqual(result["total_providers"], 3)
        self.assertEqual(result["total_matches"], 2)
        self.assertEqual(result["returned"], 1)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["next_offset"], 1)
        self.assertEqual(result["items"][0]["provider_id"], "provider-1")
        self.assertEqual(result["items"][0]["flow_ref_unit"], "kWh")

    def test_process_details_return_location_and_quantitative_reference(self) -> None:
        process_id = "process-1"
        process = olca_schema.Process(
            id=process_id,
            name="Bottle production",
            category="manufacturing",
        )
        process.location = olca_schema.Ref(id="DE", name="Germany")
        process.exchanges = [
            olca_schema.Exchange(
                flow=olca_schema.Ref(
                    id="flow-1",
                    name="Bottle",
                    ref_unit="kg",
                ),
                amount=1.0,
                unit=olca_schema.Ref(id="kg", name="kg"),
                is_input=False,
                is_quantitative_reference=True,
            ),
            olca_schema.Exchange(
                flow=olca_schema.Ref(id="flow-2", name="Electricity"),
                amount=0.5,
                is_input=True,
            ),
        ]
        client = FakeClient(
            entities={(olca_schema.Process, process_id): process},
        )
        with patch.object(readonly, "create_ipc_client", return_value=client):
            result = readonly.get_process_details(
                "localhost",
                8080,
                process_id,
            )

        self.assertTrue(result["found"])
        self.assertEqual(result["process"]["location"]["id"], "DE")
        self.assertEqual(
            result["process"]["quantitative_references"][0]["flow"]["id"],
            "flow-1",
        )
        self.assertEqual(
            result["process"]["quantitative_references"][0]["unit"]["name"],
            "kg",
        )

    def test_process_details_report_missing_process(self) -> None:
        client = FakeClient()
        with patch.object(readonly, "create_ipc_client", return_value=client):
            result = readonly.get_process_details(
                "localhost",
                8080,
                "missing-process",
            )

        self.assertFalse(result["found"])
        self.assertIsNone(result["process"])
        with self.assertRaisesRegex(ValueError, "non-empty"):
            readonly.get_process_details("localhost", 8080, "")

    def test_flow_providers_report_missing_flow_without_broad_query(self) -> None:
        client = FakeClient()
        with patch.object(readonly, "create_ipc_client", return_value=client):
            result = readonly.get_flow_providers(
                "localhost",
                8080,
                "missing-flow",
            )

        self.assertFalse(result["flow_found"])
        self.assertEqual(result["items"], [])
        with self.assertRaisesRegex(ValueError, "non-empty"):
            readonly.get_flow_providers("localhost", 8080, "")


class MCPServerTests(unittest.TestCase):
    def test_workflow_tools_are_registered_with_safe_annotations(self) -> None:
        tools = {tool.name: tool for tool in asyncio.run(mcp_module.mcp.list_tools())}

        self.assertEqual(
            set(tools),
            {
                "health_check",
                "query_descriptors",
                "get_process_details",
                "get_flow_providers",
                "preflight_import_lci",
                "import_lci",
                "get_import_operation",
                "get_model_graph",
                "calculate_product_system",
            },
        )
        self.assertTrue(tools["health_check"].annotations.read_only_hint)
        self.assertFalse(tools["health_check"].annotations.destructive_hint)
        self.assertTrue(tools["get_process_details"].annotations.read_only_hint)
        self.assertTrue(tools["get_flow_providers"].annotations.read_only_hint)
        self.assertFalse(tools["get_process_details"].annotations.destructive_hint)
        self.assertFalse(tools["get_flow_providers"].annotations.destructive_hint)
        self.assertTrue(tools["preflight_import_lci"].annotations.read_only_hint)
        self.assertFalse(tools["preflight_import_lci"].annotations.destructive_hint)
        self.assertFalse(tools["import_lci"].annotations.read_only_hint)
        self.assertTrue(tools["import_lci"].annotations.destructive_hint)
        self.assertTrue(tools["get_import_operation"].annotations.read_only_hint)
        self.assertFalse(tools["import_lci"].annotations.idempotent_hint)
        self.assertEqual(
            tools["import_lci"].input_schema["required"],
            ["preflight_hash"],
        )
        self.assertNotIn(
            "user_confirmed",
            tools["import_lci"].input_schema["properties"],
        )
        self.assertEqual(
            tools["preflight_import_lci"].input_schema["properties"]["lci_dir"]["default"],
            "workspace/outputs/LCI",
        )
        self.assertEqual(
            tools["import_lci"].input_schema["properties"]["lci_dir"]["default"],
            "workspace/outputs/LCI",
        )

    def test_workflow_lci_dir_accepts_canonical_and_tmp_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir) / "project"
            outside = Path(temp_dir) / "outside"
            canonical = project_root / "workspace" / "outputs" / "LCI"
            compatibility = project_root / "workspace" / "tmp" / "run-1" / "LCI"
            temporary_root = project_root / "workspace" / "tmp"
            temporary_root.mkdir(parents=True)
            outside.mkdir()
            (temporary_root / "unsafe-link").symlink_to(
                outside,
                target_is_directory=True,
            )
            with patch.object(mcp_module, "PROJECT_ROOT", project_root):
                self.assertEqual(
                    mcp_module._workflow_lci_dir("workspace/outputs/LCI"),
                    canonical.resolve(),
                )
                self.assertEqual(
                    mcp_module._workflow_lci_dir("workspace/tmp/run-1/LCI"),
                    compatibility.resolve(),
                )
                canonical.parent.mkdir(parents=True)
                canonical.symlink_to(outside, target_is_directory=True)
                with self.assertRaisesRegex(ValueError, "subdirectory of workspace/tmp"):
                    mcp_module._workflow_lci_dir("workspace/outputs/LCI")
                with self.assertRaisesRegex(ValueError, "subdirectory of workspace/tmp"):
                    mcp_module._workflow_lci_dir("workspace/LCI")
                with self.assertRaisesRegex(ValueError, "subdirectory of workspace/tmp"):
                    mcp_module._workflow_lci_dir("workspace/tmp")
                with self.assertRaisesRegex(ValueError, "subdirectory of workspace/tmp"):
                    mcp_module._workflow_lci_dir("workspace/tmp/../../workspace/inputs")
                with self.assertRaisesRegex(ValueError, "subdirectory of workspace/tmp"):
                    mcp_module._workflow_lci_dir(str(outside))
                with self.assertRaisesRegex(ValueError, "subdirectory of workspace/tmp"):
                    mcp_module._workflow_lci_dir("workspace/tmp/unsafe-link")

    def test_health_tool_uses_configured_endpoint(self) -> None:
        expected = {"ok": True}
        with (
            patch.dict(
                os.environ,
                {"OPENLCA_IPC_HOST": "openlca.internal", "OPENLCA_IPC_PORT": "9090"},
                clear=False,
            ),
            patch.object(mcp_module, "run_health_check", return_value=expected) as health,
        ):
            result = mcp_module.health_check()

        self.assertEqual(result, expected)
        health.assert_called_once_with("openlca.internal", 9090)

    def test_invalid_configured_port_is_rejected(self) -> None:
        with (
            patch.dict(os.environ, {"OPENLCA_IPC_PORT": "not-a-port"}, clear=False),
            self.assertRaisesRegex(ValueError, "must be an integer"),
        ):
            mcp_module.health_check()


if __name__ == "__main__":
    unittest.main()
