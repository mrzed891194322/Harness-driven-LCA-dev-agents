from __future__ import annotations

import asyncio
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import olca_schema

from harness.tools.control_openlca import main as mcp_module
from harness.tools.control_openlca.utils import connection
from harness.tools.control_openlca.utils import readonly


class FakeClient:
    def __init__(self, descriptors: list[object] | None = None, error: Exception | None = None) -> None:
        self.descriptors = descriptors or []
        self.error = error
        self.requested_type: type | None = None

    def get_descriptors(self, model_type: type) -> list[object]:
        self.requested_type = model_type
        if self.error is not None:
            raise self.error
        return self.descriptors


class ReadOnlyServiceTests(unittest.TestCase):
    def test_build_endpoint_validates_and_formats_hosts(self) -> None:
        self.assertEqual(connection.build_endpoint("localhost", 8080), "http://localhost:8080")
        self.assertEqual(connection.build_endpoint("::1", 8080), "http://[::1]:8080")
        with self.assertRaisesRegex(ValueError, "not a URL"):
            connection.build_endpoint("http://localhost", 8080)
        with self.assertRaisesRegex(ValueError, "between 1 and 65535"):
            connection.build_endpoint("localhost", 0)

    def test_probe_ipc_reuses_client_and_resolves_model_name(self) -> None:
        client = FakeClient()
        with patch.object(connection.olca_ipc, "Client", return_value=client) as client_factory:
            result = connection.probe_ipc("localhost", 8080, "Process")

        self.assertIs(result, client)
        self.assertIs(client.requested_type, olca_schema.Process)
        client_factory.assert_called_once_with("http://localhost:8080")

    def test_health_check_returns_success(self) -> None:
        with patch.object(readonly, "probe_ipc") as probe:
            result = readonly.health_check("127.0.0.1", 8080)

        self.assertTrue(result["ok"])
        self.assertEqual(result["endpoint"], "http://127.0.0.1:8080")
        probe.assert_called_once_with("127.0.0.1", 8080, olca_schema.Process)

    def test_health_check_returns_diagnostics_on_connection_failure(self) -> None:
        with patch.object(readonly, "probe_ipc", side_effect=OSError("connection refused")):
            result = readonly.health_check("127.0.0.1", 8080)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "OSError")
        self.assertIn("connection refused", result["error"])
        self.assertEqual(len(result["diagnostics"]), 3)

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


class MCPServerTests(unittest.TestCase):
    def test_workflow_tools_are_registered_with_safe_annotations(self) -> None:
        tools = {tool.name: tool for tool in asyncio.run(mcp_module.mcp.list_tools())}

        self.assertEqual(
            set(tools),
            {
                "health_check",
                "query_descriptors",
                "preflight_import_lci",
                "import_lci",
                "get_model_graph",
                "calculate_product_system",
            },
        )
        self.assertTrue(tools["health_check"].annotations.read_only_hint)
        self.assertFalse(tools["health_check"].annotations.destructive_hint)
        self.assertTrue(tools["preflight_import_lci"].annotations.read_only_hint)
        self.assertFalse(tools["preflight_import_lci"].annotations.destructive_hint)
        self.assertFalse(tools["import_lci"].annotations.read_only_hint)
        self.assertTrue(tools["import_lci"].annotations.destructive_hint)
        self.assertFalse(tools["import_lci"].annotations.idempotent_hint)

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
