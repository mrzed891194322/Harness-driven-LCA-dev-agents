from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import olca_schema
import requests

from harness.tools.control_openlca.utils import workflow
from tests.support.openlca_fakes import (
    FLOW_ID,
    GENERATED_SYSTEM_ID,
    PRODUCT_SYSTEM_ID,
    PROVIDER_ID,
    FakeDescriptor,
    FakeImportClient,
    run_import,
    write_flow,
    write_linked_auto_product_system_fixture,
    write_product_system_fixture,
)


class ImportWorkflowTests(unittest.TestCase):
    def test_lci_validation_rejects_aggregate_and_missing_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "flows.json").write_text(
                json.dumps({"flows": [{"@type": "Flow"}]}),
                encoding="utf-8",
            )
            result = workflow.validate_lci_directory(root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("only allowed" in error for error in result["errors"]))

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_flow(root)
            flow_path = next((root / "flows").glob("*.json"))
            data = json.loads(flow_path.read_text(encoding="utf-8"))
            del data["@context"]
            flow_path.write_text(json.dumps(data), encoding="utf-8")
            _, errors = workflow.load_lci_inventory(root)
        self.assertTrue(any("@context" in error for error in errors))

    def test_lci_validation_rejects_unlinked_foreground_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_product_system_fixture(root)
            (root / "human_readable_mapping.md").write_text(
                "# Mapping\n",
                encoding="utf-8",
            )
            process_path = root / "processes" / "p01-test.json"
            process = json.loads(process_path.read_text(encoding="utf-8"))
            process["exchanges"] = [
                {
                    "@type": "Exchange",
                    "flow": {"@type": "Flow", "@id": FLOW_ID},
                    "isInput": True,
                }
            ]
            process_path.write_text(json.dumps(process), encoding="utf-8")
            result = workflow.validate_lci_directory(root)

        self.assertFalse(result["ok"])
        self.assertTrue(
            any("requires defaultProvider" in error for error in result["errors"])
        )

    def test_lci_validation_requires_boolean_is_input(self) -> None:
        invalid_values = (None, "true")
        for invalid in invalid_values:
            with self.subTest(value=invalid), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                write_product_system_fixture(root)
                (root / "human_readable_mapping.md").write_text(
                    "# Mapping\n",
                    encoding="utf-8",
                )
                process_path = root / "processes" / "p01-test.json"
                process = json.loads(process_path.read_text(encoding="utf-8"))
                process["exchanges"] = [
                    {
                        "@type": "Exchange",
                        "flow": {"@type": "Flow", "@id": FLOW_ID},
                        "isInput": invalid,
                    }
                ]
                process_path.write_text(json.dumps(process), encoding="utf-8")
                result = workflow.validate_lci_directory(root)

            self.assertFalse(result["ok"])
            self.assertTrue(
                any(
                    "isInput must be an explicit boolean" in error
                    for error in result["errors"]
                )
            )

    def test_lci_validation_rejects_ignored_input_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_product_system_fixture(root)
            (root / "human_readable_mapping.md").write_text(
                "# Mapping\n",
                encoding="utf-8",
            )
            process_path = root / "processes" / "p01-test.json"
            process = json.loads(process_path.read_text(encoding="utf-8"))
            process["exchanges"] = [
                {
                    "@type": "Exchange",
                    "flow": {"@type": "Flow", "@id": FLOW_ID},
                    "input": True,
                }
            ]
            process_path.write_text(json.dumps(process), encoding="utf-8")
            result = workflow.validate_lci_directory(root)

        self.assertFalse(result["ok"])
        self.assertTrue(
            any("unsupported field 'input'" in error for error in result["errors"])
        )

    def test_preflight_rejects_ignored_quantitative_reference_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_product_system_fixture(root)
            process_path = root / "processes" / "p01-test.json"
            process = json.loads(process_path.read_text(encoding="utf-8"))
            exchange = process["exchanges"][0]
            del exchange["isQuantitativeReference"]
            exchange["quantitativeReference"] = True
            process_path.write_text(json.dumps(process), encoding="utf-8")
            client = FakeImportClient()
            result = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "invalid_lci")
        self.assertNotIn("preflight_hash", result)
        self.assertTrue(
            any(
                "unsupported field 'quantitativeReference'" in error
                for error in result["errors"]
            )
        )
        self.assertEqual(client.put_calls, [])
        self.assertEqual(client.delete_calls, [])

    def test_lci_validation_requires_one_output_quantitative_reference(self) -> None:
        cases = ("missing", "duplicate", "input")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                write_product_system_fixture(root)
                (root / "human_readable_mapping.md").write_text(
                    "# Mapping\n",
                    encoding="utf-8",
                )
                process_path = root / "processes" / "p01-test.json"
                process = json.loads(process_path.read_text(encoding="utf-8"))
                exchange = process["exchanges"][0]
                if case == "missing":
                    del exchange["isQuantitativeReference"]
                elif case == "duplicate":
                    process["exchanges"].append(dict(exchange))
                else:
                    exchange["isInput"] = True
                process_path.write_text(json.dumps(process), encoding="utf-8")
                result = workflow.validate_lci_directory(root)

            self.assertFalse(result["ok"])
            if case == "missing":
                self.assertTrue(any("found 0" in error for error in result["errors"]))
            elif case == "duplicate":
                self.assertTrue(any("found 2" in error for error in result["errors"]))
            else:
                self.assertTrue(
                    any(
                        "quantitative reference must be an output exchange" in error
                        for error in result["errors"]
                    )
                )

    def test_lci_validation_checks_quantitative_reference_shape(self) -> None:
        cases = ("non_boolean", "missing_flow")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                write_product_system_fixture(root)
                (root / "human_readable_mapping.md").write_text(
                    "# Mapping\n",
                    encoding="utf-8",
                )
                process_path = root / "processes" / "p01-test.json"
                process = json.loads(process_path.read_text(encoding="utf-8"))
                exchange = process["exchanges"][0]
                if case == "non_boolean":
                    exchange["isQuantitativeReference"] = "true"
                else:
                    del exchange["flow"]
                process_path.write_text(json.dumps(process), encoding="utf-8")
                result = workflow.validate_lci_directory(root)

            self.assertFalse(result["ok"])
            expected = (
                "isQuantitativeReference must be a boolean"
                if case == "non_boolean"
                else "requires a non-empty Flow @id"
            )
            self.assertTrue(any(expected in error for error in result["errors"]))

    def test_lci_validation_requires_foreground_provider_to_output_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_linked_auto_product_system_fixture(root)
            (root / "human_readable_mapping.md").write_text(
                "# Mapping\n",
                encoding="utf-8",
            )
            provider_path = root / "processes" / "p02-provider.json"
            provider = json.loads(provider_path.read_text(encoding="utf-8"))
            provider["exchanges"][0]["flow"]["@id"] = "different-flow"
            provider_path.write_text(json.dumps(provider), encoding="utf-8")
            result = workflow.validate_lci_directory(root)

        self.assertFalse(result["ok"])
        self.assertTrue(
            any(
                "does not output foreground Flow" in error for error in result["errors"]
            )
        )

    def test_preflight_is_read_only_and_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_flow(root)
            client = FakeImportClient(
                {"Flow": [FakeDescriptor("old-flow", "Old", "project-a")]}
            )
            first = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )
            second = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )

        self.assertTrue(first["ok"])
        self.assertEqual(first["active_database"], second["active_database"])
        self.assertEqual(first["target_category"], second["target_category"])
        self.assertEqual(first["lci_dir"], second["lci_dir"])
        self.assertNotIn("preflight_hash", first)
        self.assertEqual(first["counts"], {"planned": 1, "overwrite_or_delete": 1})
        self.assertEqual(client.put_calls, [])
        self.assertEqual(client.delete_calls, [])

    def test_preflight_owned_client_uses_long_timeout_and_closes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_flow(root)
            client = FakeImportClient()
            with patch.object(
                workflow,
                "create_ipc_client",
                return_value=client,
            ) as client_factory:
                result = workflow.preflight_import_lci(
                    "localhost",
                    8080,
                    root,
                    "project-a",
                    "isolated-db",
                )

        self.assertTrue(result["ok"], result["errors"])
        client_factory.assert_called_once_with("localhost", 8080)
        self.assertEqual(client.close_calls, 1)

    def test_preflight_owned_client_closes_after_snapshot_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_flow(root)
            client = FakeImportClient()
            client.query_error = OSError("wrong database")
            with (
                patch.object(
                    workflow,
                    "create_ipc_client",
                    return_value=client,
                ) as client_factory,
                self.assertRaisesRegex(RuntimeError, "http://localhost:8080"),
            ):
                workflow.preflight_import_lci(
                    "localhost",
                    8080,
                    root,
                    "project-a",
                    "isolated-db",
                )

        client_factory.assert_called_once_with("localhost", 8080)
        self.assertEqual(client.close_calls, 1)

    def test_unrelated_database_changes_do_not_change_import_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_flow(root)
            client = FakeImportClient()
            first = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )
            client.descriptors["Process"] = [
                FakeDescriptor("background-process", "Unrelated", "background")
            ]
            second = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )

        self.assertEqual(first["active_database"], second["active_database"])
        self.assertEqual(first["target_category"], second["target_category"])
        self.assertEqual(first["lci_dir"], second["lci_dir"])
        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])

    def test_preflight_requires_explicit_database_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_flow(root)
            with patch.dict(
                os.environ,
                {"OPENLCA_DATABASE_NAME": ""},
                clear=False,
            ):
                result = workflow.preflight_import_lci(
                    "localhost", 8080, root, "project-a", None, FakeImportClient()
                )
        self.assertFalse(result["ok"])
        self.assertEqual(result["database_identity_source"], "missing")
        self.assertTrue(any("database identity" in error for error in result["errors"]))

    def test_preflight_validates_and_fingerprints_background_providers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_product_system_fixture(root)
            process_path = root / "processes" / "p01-test.json"
            process_data = json.loads(process_path.read_text(encoding="utf-8"))
            process_data["exchanges"] = [
                {
                    "@type": "Exchange",
                    "flow": {
                        "@type": "Flow",
                        "@id": FLOW_ID,
                        "name": "Test product",
                    },
                    "isInput": False,
                    "isQuantitativeReference": True,
                },
                {
                    "@type": "Exchange",
                    "flow": {"@type": "Flow", "@id": FLOW_ID, "name": "Test product"},
                    "defaultProvider": {
                        "@type": "Process",
                        "@id": PROVIDER_ID,
                        "name": "Background provider",
                    },
                    "expectedProviderGeography": "RoW",
                    "isInput": True,
                },
            ]
            process_path.write_text(json.dumps(process_data), encoding="utf-8")
            client = FakeImportClient(
                {
                    "Process": [
                        FakeDescriptor(PROVIDER_ID, "Background provider", "background")
                    ]
                }
            )
            provider = olca_schema.Process(
                id=PROVIDER_ID,
                name="Background provider",
            )
            provider.location = olca_schema.Ref(
                id="rest-of-world",
                name="Rest of World",
            )
            provider.exchanges = [
                olca_schema.Exchange(
                    flow=olca_schema.Ref(id=FLOW_ID, name="Test product"),
                    is_input=False,
                )
            ]
            client.entities[(olca_schema.Process, PROVIDER_ID)] = provider
            first = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )
            provider.exchanges = [
                olca_schema.Exchange(
                    flow=olca_schema.Ref(id="different-flow", name="Different"),
                    is_input=False,
                )
            ]
            second = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )
            client.descriptors["Process"] = []
            third = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )

        self.assertTrue(first["ok"])
        self.assertTrue(first["background_provider_checks"][0]["output_flow_match"])
        self.assertFalse(first["background_provider_checks"][0]["geography_match"])
        self.assertFalse(second["ok"])
        self.assertFalse(third["ok"])
        self.assertTrue(
            any(
                "was not found in the active database" in error
                for error in third["errors"]
            )
        )
        self.assertNotIn("background_provider_fingerprint", first)
        self.assertNotIn("preflight_hash", first)

    def test_import_rejects_unmatched_scope_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            operation_dir = Path(temp_dir) / "operations"
            write_flow(root)
            client = FakeImportClient()
            preflight = workflow.preflight_import_lci(
                "localhost",
                8080,
                root,
                "project-a",
                "isolated-db",
                client,
                operation_dir,
            )
            report = run_import(
                root,
                client,
                category="other-project",
                operation_dir=operation_dir,
            )

        self.assertTrue(preflight["ok"])
        self.assertEqual(report["status"], "rejected")
        self.assertIn(
            "does not match the last successful preflight", report["errors"][0]
        )
        self.assertEqual(client.put_calls, [])
        self.assertEqual(client.delete_calls, [])

    def test_changed_lci_content_keeps_same_scope_writable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_flow(root)
            client = FakeImportClient()
            preflight = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )
            write_flow(root, name="F01 Changed product")
            report = run_import(root, client)

        self.assertTrue(preflight["ok"])
        self.assertEqual(report["status"], "success")
        self.assertGreater(len(client.put_calls), 0)

    def test_changed_overwrite_set_keeps_same_scope_writable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_flow(root)
            client = FakeImportClient()
            preflight = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )
            client.descriptors["Flow"] = [
                FakeDescriptor("new-old", "Existing", "project-a")
            ]
            report = run_import(root, client)

        self.assertTrue(preflight["ok"])
        self.assertEqual(report["status"], "success")
        self.assertGreater(len(client.put_calls), 0)

    def test_success_partial_failure_and_repeated_execution_are_structured(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_flow(root)
            client = FakeImportClient(
                {"Flow": [FakeDescriptor("old-flow", "Old", "project-a")]}
            )
            first = run_import(root, client)
            second = run_import(root, client)
            write_flow(
                root,
                name="F02 Failing product",
                entity_id="22222222-2222-4222-8222-222222222222",
                filename="f02-failing-product.json",
            )
            client.fail_put_names.add("F02 Failing product")
            failed = run_import(root, client)

        self.assertEqual(first["status"], "success")
        self.assertEqual(second["status"], "success")
        self.assertEqual(first["success_count"], 1)
        self.assertEqual(first["deleted_count"], 1)
        self.assertEqual(failed["status"], "partial_failure")
        self.assertEqual(failed["failed_count"], 1)
        self.assertEqual(failed["success_count"], 1)

    def test_import_stops_immediately_after_transport_failure(self) -> None:
        client = FakeImportClient()
        client.put_error = requests.ConnectionError("connection lost")
        inventory = [
            {
                "path": f"flows/f0{index}.json",
                "entity_type": "Flow",
                "id": f"flow-{index}",
                "name": f"Flow {index}",
                "data": {
                    "@type": "Flow",
                    "@id": f"flow-{index}",
                    "name": f"Flow {index}",
                },
            }
            for index in (1, 2)
        ]

        records, imported, failed, deleted, errors = workflow._execute_import(
            client,
            inventory,
            [],
            "project-a",
        )

        self.assertEqual(len(client.put_calls), 1)
        self.assertEqual(len(records), 1)
        self.assertEqual((imported, failed, deleted), (0, 1, 0))
        self.assertIn("connection lost", errors[0])

    def test_import_continues_after_read_timeout_on_single_entity(self) -> None:
        client = FakeImportClient()
        attempts = {"count": 0}
        original_put = client.put

        def slow_put(entity: object) -> SimpleNamespace | None:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise requests.Timeout("slow openlca")
            return original_put(entity)

        client.put = slow_put
        inventory = [
            {
                "path": f"flows/f0{index}.json",
                "entity_type": "Flow",
                "id": f"flow-{index}",
                "name": f"Flow {index}",
                "data": {
                    "@type": "Flow",
                    "@id": f"flow-{index}",
                    "name": f"Flow {index}",
                },
            }
            for index in (1, 2)
        ]

        records, imported, failed, deleted, errors = workflow._execute_import(
            client,
            inventory,
            [],
            "project-a",
        )

        self.assertEqual(attempts["count"], 2)
        self.assertEqual(len(records), 2)
        self.assertEqual((imported, failed, deleted), (1, 1, 0))
        self.assertIn("slow openlca", errors[0])

    def test_product_system_uses_official_auto_linking_and_preserves_uuid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_product_system_fixture(root)
            client = FakeImportClient()
            report = run_import(root, client)

        self.assertEqual(report["status"], "success")
        self.assertEqual(report["success_count"], 3)
        self.assertEqual(len(client.create_product_system_calls), 1)
        _, config_raw = client.create_product_system_calls[0]
        assert isinstance(config_raw, olca_schema.LinkingConfig)
        config = config_raw
        self.assertEqual(
            config.provider_linking,
            olca_schema.ProviderLinking.PREFER_DEFAULTS,
        )
        saved_raw = client.entities[(olca_schema.ProductSystem, PRODUCT_SYSTEM_ID)]
        assert isinstance(saved_raw, olca_schema.ProductSystem)
        saved = saved_raw
        self.assertEqual(saved.name, "PS01 Test product system")
        self.assertEqual(saved.description, "Preserve this metadata")
        self.assertEqual(saved.target_amount, 1065.0)
        self.assertEqual(len(saved.processes or []), 2)
        self.assertEqual(len(saved.process_links or []), 1)
        graph = workflow.model_graph_from_product_system(saved, "http://localhost:8080")
        self.assertEqual(graph["status"], "success")
        self.assertEqual(len(graph["nodes"]), 2)
        self.assertEqual(len(graph["edges"]), 1)
        self.assertNotIn(
            (olca_schema.ProductSystem, GENERATED_SYSTEM_ID),
            client.entities,
        )
        self.assertTrue(
            any(
                getattr(reference, "id", None) == GENERATED_SYSTEM_ID
                for reference in client.delete_calls
            )
        )

    def test_product_system_create_timeout_recovers_declared_system(self) -> None:
        client = FakeImportClient()
        recovered = olca_schema.ProductSystem(
            id=PRODUCT_SYSTEM_ID,
            name="Recovered system",
        )
        recovered.processes = [olca_schema.Ref(id=PROVIDER_ID, name="Default provider")]
        recovered.process_links = []
        client.entities[(olca_schema.ProductSystem, PRODUCT_SYSTEM_ID)] = recovered

        def timeout_create(process: object, config: object) -> SimpleNamespace:
            raise requests.Timeout("linking still running")

        client.create_product_system = timeout_create
        entity = olca_schema.ProductSystem(
            id=PRODUCT_SYSTEM_ID,
            name="Recovered system",
        )
        entity.ref_process = olca_schema.Ref(id=PROVIDER_ID)
        reference = workflow._put_product_system(
            client,
            entity,
            {"linkingMode": "auto", "preferDefaultProviders": True},
        )
        self.assertEqual(getattr(reference, "id", None), PRODUCT_SYSTEM_ID)

    def test_product_system_uses_defaults_for_foreground_auto_linking(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_linked_auto_product_system_fixture(root)
            (root / "human_readable_mapping.md").write_text(
                "# LCI mapping\n",
                encoding="utf-8",
            )
            validation = workflow.validate_lci_directory(root)
            client = FakeImportClient()
            report = run_import(root, client)

        self.assertTrue(validation["ok"], validation["errors"])
        self.assertEqual(report["status"], "success")
        self.assertEqual(len(client.create_product_system_calls), 1)
        saved_raw = client.entities[(olca_schema.ProductSystem, PRODUCT_SYSTEM_ID)]
        assert isinstance(saved_raw, olca_schema.ProductSystem)
        saved = saved_raw
        self.assertEqual(len(saved.processes or []), 2)
        self.assertEqual(len(saved.process_links or []), 1)

    def test_lci_validation_rejects_explicit_product_system(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_product_system_fixture(root)
            (root / "human_readable_mapping.md").write_text(
                "# LCI mapping\n",
                encoding="utf-8",
            )
            path = root / "product_systems" / "ps01-test.json"
            product_system = json.loads(path.read_text(encoding="utf-8"))
            product_system["linkingMode"] = "explicit"
            product_system["processLinks"] = [{"provider": {"@id": PROVIDER_ID}}]
            path.write_text(json.dumps(product_system), encoding="utf-8")
            result = workflow.validate_lci_directory(root)

        self.assertFalse(result["ok"])
        self.assertTrue(
            any(
                "linkingMode must be explicitly set to 'auto'" in error
                for error in result["errors"]
            )
        )

    def test_import_operation_journal_prevents_blind_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "lci"
            operation_dir = Path(temp_dir) / "operations"
            write_flow(root)
            client = FakeImportClient()
            first = run_import(root, client, operation_dir=operation_dir)
            put_count = len(client.put_calls)
            repeated = run_import(root, client, operation_dir=operation_dir)
            status = workflow.get_import_operation(operation_dir)

        self.assertEqual(first["status"], "success")
        self.assertEqual(repeated["operation_id"], first["operation_id"])
        self.assertEqual(status["status"], "success")
        self.assertEqual(len(client.put_calls), put_count)

    def test_product_system_auto_link_failure_is_structured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_product_system_fixture(root)
            client = FakeImportClient()
            client.fail_create_product_system = True
            report = run_import(root, client)

        self.assertEqual(report["status"], "partial_failure")
        self.assertEqual(report["failed_count"], 1)
        self.assertIn(
            "did not create an auto-linked ProductSystem", report["errors"][0]
        )

    def test_product_system_auto_link_report_preserves_rpc_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_product_system_fixture(root)
            client = FakeImportClient()
            client.create_product_system_error = RuntimeError(
                "reference process has no quantitative reference"
            )
            report = run_import(root, client)

        self.assertEqual(report["status"], "partial_failure")
        self.assertEqual(report["failed_count"], 1)
        self.assertIn(
            "reference process has no quantitative reference",
            report["errors"][0],
        )

    def test_product_system_temporary_cleanup_failure_is_structured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_product_system_fixture(root)
            client = FakeImportClient()
            client.fail_delete_ids.add(GENERATED_SYSTEM_ID)
            report = run_import(root, client)

        self.assertEqual(report["status"], "partial_failure")
        self.assertEqual(report["failed_count"], 1)
        self.assertIn("could not delete temporary system", report["errors"][0])

    def test_database_query_error_is_structured_with_endpoint_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_flow(root)
            client = FakeImportClient()
            client.query_error = OSError("wrong database")
            with self.assertRaisesRegex(RuntimeError, "http://localhost:8080"):
                workflow.preflight_import_lci(
                    "localhost", 8080, root, "project-a", "isolated-db", client
                )

    def test_legacy_cli_service_continues_after_invalid_file_or_descriptor_warning(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_flow(root)
            (root / "invalid.json").write_text("{not-json", encoding="utf-8")
            client = FakeImportClient()
            client.query_error = OSError("descriptor unavailable")
            messages: list[str] = []
            result = workflow.legacy_import_lci(
                client, root, "project-a", emit=messages.append
            )

        self.assertEqual(result["success_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(len(client.put_calls), 1)
        self.assertTrue(any("only allowed" in message for message in messages))
        self.assertTrue(any("描述符失败" in message for message in messages))


class GraphClient:
    def __init__(self, product_system: olca_schema.ProductSystem) -> None:
        self.product_system = product_system

    def get(self, model_type: type, _identifier: str) -> object | None:
        if model_type is olca_schema.ProductSystem:
            return self.product_system
        return None


class GraphWorkflowTests(unittest.TestCase):
    def test_graph_requires_declared_scenario_processes(self) -> None:
        system = olca_schema.ProductSystem(id="ps-id", name="PS1 Scenario")
        system.processes = [
            olca_schema.Ref(id="p1", name="P1"),
            olca_schema.Ref(id="p2", name="P2"),
        ]
        system.process_links = [
            olca_schema.ProcessLink(
                provider=olca_schema.Ref(id="p1", name="P1"),
                process=olca_schema.Ref(id="p2", name="P2"),
                flow=olca_schema.Ref(id="f1", name="F1"),
            )
        ]
        result = workflow.get_model_graph(
            "localhost",
            8080,
            "ps-id",
            GraphClient(system),
            expected_process_ids=["p1", "train-process"],
        )

        self.assertEqual(result["status"], "broken")
        self.assertEqual(result["missing_expected_nodes"], ["train-process"])
        self.assertNotIn("graph_fingerprint", result)

    def test_graph_reports_broken_links(self) -> None:
        system = olca_schema.ProductSystem(id="ps-id", name="PS1 Test")
        system.processes = [olca_schema.Ref(id="p1", name="P1")]
        system.process_links = [
            olca_schema.ProcessLink(
                provider=olca_schema.Ref(id="missing", name="Missing"),
                process=olca_schema.Ref(id="p1", name="P1"),
                flow=olca_schema.Ref(id="f1", name="F1"),
            )
        ]
        result = workflow.get_model_graph(
            "localhost", 8080, "ps-id", GraphClient(system)
        )

        self.assertEqual(result["status"], "broken")
        self.assertEqual(result["product_system"]["id"], "ps-id")
        self.assertEqual(len(result["broken_links"]), 1)

    def test_graph_rejects_empty_nodes(self) -> None:
        system = olca_schema.ProductSystem(id="ps-id", name="PS1 Empty")
        result = workflow.get_model_graph(
            "localhost", 8080, "ps-id", GraphClient(system)
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["nodes"], [])
        self.assertIn("no process nodes", result["error"])

    def test_graph_reports_disconnected_nodes_as_broken(self) -> None:
        system = olca_schema.ProductSystem(id="ps-id", name="PS1 Disconnected")
        system.processes = [
            olca_schema.Ref(id="p1", name="P1"),
            olca_schema.Ref(id="p2", name="P2"),
        ]
        result = workflow.get_model_graph(
            "localhost", 8080, "ps-id", GraphClient(system)
        )

        self.assertEqual(result["status"], "broken")
        self.assertEqual(len(result["disconnected_nodes"]), 2)

    def test_graph_owned_client_uses_session_timeout_and_closes(self) -> None:
        system = olca_schema.ProductSystem(id="ps-id", name="PS1 Owned")
        system.processes = [
            olca_schema.Ref(id="p1", name="P1"),
            olca_schema.Ref(id="p2", name="P2"),
        ]
        system.process_links = [
            olca_schema.ProcessLink(
                provider=olca_schema.Ref(id="p1", name="P1"),
                process=olca_schema.Ref(id="p2", name="P2"),
                flow=olca_schema.Ref(id="f1", name="F1"),
            )
        ]
        client = GraphClient(system)
        client.close_calls = 0

        def close() -> None:
            client.close_calls += 1

        client.close = close
        with patch.object(
            workflow,
            "create_ipc_client",
            return_value=client,
        ) as client_factory:
            result = workflow.get_model_graph("localhost", 8080, "ps-id")

        self.assertEqual(result["status"], "success")
        client_factory.assert_called_once_with("localhost", 8080)
        self.assertEqual(client.close_calls, 1)


class FakeResult:
    def __init__(
        self, impacts: list[object] | None = None, error: Exception | None = None
    ) -> None:
        self.impacts = impacts or []
        self.error = error
        self.disposed = False

    def wait_until_ready(self) -> None:
        return None

    def get_total_impacts(self) -> list[object]:
        if self.error is not None:
            raise self.error
        return self.impacts

    def dispose(self) -> None:
        self.disposed = True


class CalculationClient:
    def __init__(self, result: FakeResult) -> None:
        self.system = olca_schema.ProductSystem(id="ps-id", name="PS1 Test")
        self.method = olca_schema.ImpactMethod(id="method-id", name="EF Test")
        self.result = result

    def get(self, model_type: type, _identifier: str) -> object | None:
        if model_type is olca_schema.ProductSystem:
            return self.system
        if model_type is olca_schema.ImpactMethod:
            return self.method
        return None

    def calculate(self, _setup: object) -> FakeResult:
        return self.result


class CalculationWorkflowTests(unittest.TestCase):
    def test_nonempty_calculation_releases_handle(self) -> None:
        category = olca_schema.Ref(
            id="impact-id", name="Climate change", ref_unit="kg CO2-eq"
        )
        result_handle = FakeResult(
            [SimpleNamespace(impact_category=category, amount=1.25)]
        )
        result = workflow.calculate_product_system(
            "localhost",
            8080,
            "ps-id",
            "method-id",
            client=CalculationClient(result_handle),
        )

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["resource_released"])
        self.assertTrue(result_handle.disposed)
        self.assertEqual(result["impact_categories"][0]["id"], "impact-id")

    def test_empty_and_error_results_do_not_pass_and_release_handle(self) -> None:
        empty_handle = FakeResult([])
        empty = workflow.calculate_product_system(
            "localhost",
            8080,
            "ps-id",
            "method-id",
            client=CalculationClient(empty_handle),
        )
        error_handle = FakeResult(error=RuntimeError("calculation failed"))
        failed = workflow.calculate_product_system(
            "localhost",
            8080,
            "ps-id",
            "method-id",
            client=CalculationClient(error_handle),
        )

        self.assertEqual(empty["status"], "empty")
        self.assertTrue(empty["resource_released"])
        self.assertEqual(failed["status"], "failed")
        self.assertTrue(failed["resource_released"])
        self.assertIn("calculation failed", failed["error"])


if __name__ == "__main__":
    unittest.main()
