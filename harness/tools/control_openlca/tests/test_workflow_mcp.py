from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import olca_schema

from harness.tools.control_openlca.utils import workflow


FLOW_ID = "11111111-1111-4111-8111-111111111111"
PROCESS_ID = "22222222-2222-4222-8222-222222222222"
PRODUCT_SYSTEM_ID = "33333333-3333-4333-8333-333333333333"
GENERATED_SYSTEM_ID = "44444444-4444-4444-8444-444444444444"
PROVIDER_ID = "55555555-5555-4555-8555-555555555555"


class FakeDescriptor:
    def __init__(self, entity_id: str, name: str, category: str | None = None) -> None:
        self.id = entity_id
        self.name = name
        self.category = category

    def to_ref(self) -> SimpleNamespace:
        return SimpleNamespace(id=self.id, name=self.name)


class FakeImportClient:
    def __init__(self, descriptors: dict[str, list[FakeDescriptor]] | None = None) -> None:
        self.descriptors = descriptors or {}
        self.put_calls: list[object] = []
        self.delete_calls: list[object] = []
        self.fail_put = False
        self.fail_put_names: set[str] = set()
        self.fail_delete_ids: set[str] = set()
        self.fail_create_product_system = False
        self.query_error: Exception | None = None
        self.create_product_system_calls: list[tuple[object, object]] = []
        self.entities: dict[tuple[type, str], object] = {}

    def get_descriptors(self, model_type: type) -> list[FakeDescriptor]:
        if self.query_error is not None:
            raise self.query_error
        return list(self.descriptors.get(model_type.__name__, []))

    def put(self, entity: object) -> SimpleNamespace | None:
        self.put_calls.append(entity)
        if self.fail_put or getattr(entity, "name", None) in self.fail_put_names:
            return None
        entity_type = type(entity).__name__
        self.descriptors.setdefault(entity_type, []).append(
            FakeDescriptor(
                getattr(entity, "id", None),
                getattr(entity, "name", None),
                getattr(entity, "category", None),
            )
        )
        entity_id = getattr(entity, "id", None)
        if entity_id:
            self.entities[(type(entity), entity_id)] = entity
        return SimpleNamespace(id=getattr(entity, "id", None))

    def create_product_system(
        self, process: object, config: object
    ) -> SimpleNamespace | None:
        self.create_product_system_calls.append((process, config))
        if self.fail_create_product_system:
            return None
        generated = olca_schema.ProductSystem(
            id=GENERATED_SYSTEM_ID,
            name="Generated product system",
        )
        generated.processes = [
            olca_schema.Ref(id=PROCESS_ID, name="Foreground process"),
            olca_schema.Ref(id=PROVIDER_ID, name="Default provider"),
        ]
        generated.process_links = [
            olca_schema.ProcessLink(
                provider=olca_schema.Ref(id=PROVIDER_ID, name="Default provider"),
                process=olca_schema.Ref(id=PROCESS_ID, name="Foreground process"),
                flow=olca_schema.Ref(id=FLOW_ID, name="Test product"),
            )
        ]
        generated.ref_process = olca_schema.Ref(id=PROCESS_ID)
        generated.target_amount = 1.0
        self.entities[(olca_schema.ProductSystem, GENERATED_SYSTEM_ID)] = generated
        return SimpleNamespace(id=GENERATED_SYSTEM_ID)

    def get(self, model_type: type, identifier: str) -> object | None:
        return self.entities.get((model_type, identifier))

    def delete(self, reference: object) -> None:
        self.delete_calls.append(reference)
        reference_id = getattr(reference, "id", None)
        if reference_id in self.fail_delete_ids:
            raise RuntimeError(f"cannot delete {reference_id}")
        for key in list(self.entities):
            if key[1] == reference_id:
                del self.entities[key]
        for entity_type, descriptors in self.descriptors.items():
            self.descriptors[entity_type] = [
                descriptor
                for descriptor in descriptors
                if descriptor.id != getattr(reference, "id", None)
            ]


def write_flow(
    root: Path,
    name: str = "F01 Test product",
    entity_id: str = FLOW_ID,
    filename: str = "f01-test-product.json",
) -> None:
    flows = root / "flows"
    flows.mkdir(parents=True, exist_ok=True)
    (flows / filename).write_text(
        json.dumps(
            {
                "@type": "Flow",
                "@id": entity_id,
                "name": name,
                "flowType": "PRODUCT_FLOW",
            }
        ),
        encoding="utf-8",
    )


def write_product_system_fixture(root: Path) -> None:
    write_flow(root)
    processes = root / "processes"
    product_systems = root / "product_systems"
    processes.mkdir(parents=True, exist_ok=True)
    product_systems.mkdir(parents=True, exist_ok=True)
    (processes / "p01-test.json").write_text(
        json.dumps(
            {
                "@type": "Process",
                "@id": PROCESS_ID,
                "name": "P01 Foreground process",
                "exchanges": [],
            }
        ),
        encoding="utf-8",
    )
    (product_systems / "ps01-test.json").write_text(
        json.dumps(
            {
                "@type": "ProductSystem",
                "@id": PRODUCT_SYSTEM_ID,
                "name": "PS01 Test product system",
                "description": "Preserve this metadata",
                "refProcess": {"@type": "Process", "@id": PROCESS_ID},
                "targetAmount": 1065.0,
                "preferDefaultProviders": True,
            }
        ),
        encoding="utf-8",
    )


class ImportWorkflowTests(unittest.TestCase):
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
        self.assertEqual(first["preflight_hash"], second["preflight_hash"])
        self.assertEqual(first["counts"], {"planned": 1, "overwrite_or_delete": 1})
        self.assertEqual(client.put_calls, [])
        self.assertEqual(client.delete_calls, [])

    def test_import_rejects_unmatched_hash_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_flow(root)
            client = FakeImportClient()
            report = workflow.import_lci(
                "localhost",
                8080,
                root,
                "project-a",
                "0" * 64,
                "isolated-db",
                client,
            )

        self.assertEqual(report["status"], "rejected")
        self.assertEqual(client.put_calls, [])
        self.assertEqual(client.delete_calls, [])

    def test_import_rejects_malformed_preflight_hash(self) -> None:
        client = FakeImportClient()
        with self.assertRaisesRegex(ValueError, "64-character SHA-256"):
            workflow.import_lci(
                "localhost", 8080, ".", "project-a", "not-a-hash", "isolated-db", client
            )
        self.assertEqual(client.put_calls, [])
        self.assertEqual(client.delete_calls, [])

    def test_changed_lci_or_scope_rejects_old_hash_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_flow(root)
            client = FakeImportClient()
            preflight = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )
            write_flow(root, name="F01 Changed product")
            report = workflow.import_lci(
                "localhost",
                8080,
                root,
                "project-a",
                preflight["preflight_hash"],
                "isolated-db",
                client,
            )

        self.assertEqual(report["status"], "rejected")
        self.assertIn("hash mismatch", report["errors"][0])
        self.assertEqual(client.put_calls, [])
        self.assertEqual(client.delete_calls, [])

    def test_changed_database_scope_rejects_old_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_flow(root)
            client = FakeImportClient()
            preflight = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )
            client.descriptors["Flow"] = [FakeDescriptor("new-old", "Existing", "project-a")]
            report = workflow.import_lci(
                "localhost",
                8080,
                root,
                "project-a",
                preflight["preflight_hash"],
                "isolated-db",
                client,
            )

        self.assertEqual(report["status"], "rejected")
        self.assertEqual(client.put_calls, [])
        self.assertEqual(client.delete_calls, [])

    def test_success_partial_failure_and_repeated_execution_are_structured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_flow(root)
            client = FakeImportClient(
                {"Flow": [FakeDescriptor("old-flow", "Old", "project-a")]}
            )
            preflight = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )
            first = workflow.import_lci(
                "localhost", 8080, root, "project-a", preflight["preflight_hash"], "isolated-db", client
            )
            second = workflow.import_lci(
                "localhost", 8080, root, "project-a", preflight["preflight_hash"], "isolated-db", client
            )
            write_flow(
                root,
                name="F02 Failing product",
                entity_id="22222222-2222-4222-8222-222222222222",
                filename="f02-failing-product.json",
            )
            current = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )
            client.fail_put_names.add("F02 Failing product")
            failed = workflow.import_lci(
                "localhost", 8080, root, "project-a", current["preflight_hash"], "isolated-db", client
            )

        self.assertEqual(first["status"], "success")
        self.assertEqual(second["status"], "rejected")
        self.assertEqual(first["success_count"], 1)
        self.assertEqual(first["deleted_count"], 1)
        self.assertEqual(failed["status"], "partial_failure")
        self.assertEqual(failed["failed_count"], 1)
        self.assertEqual(failed["success_count"], 1)

    def test_product_system_uses_official_auto_linking_and_preserves_uuid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_product_system_fixture(root)
            client = FakeImportClient()
            preflight = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )
            report = workflow.import_lci(
                "localhost",
                8080,
                root,
                "project-a",
                preflight["preflight_hash"],
                "isolated-db",
                client,
            )

        self.assertEqual(report["status"], "success")
        self.assertEqual(report["success_count"], 3)
        self.assertEqual(len(client.create_product_system_calls), 1)
        _, config = client.create_product_system_calls[0]
        self.assertEqual(
            config.provider_linking,
            olca_schema.ProviderLinking.PREFER_DEFAULTS,
        )
        saved = client.entities[(olca_schema.ProductSystem, PRODUCT_SYSTEM_ID)]
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

    def test_product_system_auto_link_failure_is_structured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_product_system_fixture(root)
            client = FakeImportClient()
            client.fail_create_product_system = True
            preflight = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )
            report = workflow.import_lci(
                "localhost",
                8080,
                root,
                "project-a",
                preflight["preflight_hash"],
                "isolated-db",
                client,
            )

        self.assertEqual(report["status"], "partial_failure")
        self.assertEqual(report["failed_count"], 1)
        self.assertIn("did not create an auto-linked ProductSystem", report["errors"][0])

    def test_product_system_temporary_cleanup_failure_is_structured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_product_system_fixture(root)
            client = FakeImportClient()
            client.fail_delete_ids.add(GENERATED_SYSTEM_ID)
            preflight = workflow.preflight_import_lci(
                "localhost", 8080, root, "project-a", "isolated-db", client
            )
            report = workflow.import_lci(
                "localhost",
                8080,
                root,
                "project-a",
                preflight["preflight_hash"],
                "isolated-db",
                client,
            )

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

    def test_legacy_cli_service_continues_after_invalid_file_or_descriptor_warning(self) -> None:
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
        self.assertTrue(any("invalid JSON" in message for message in messages))
        self.assertTrue(any("描述符失败" in message for message in messages))


class GraphClient:
    def __init__(self, product_system: olca_schema.ProductSystem) -> None:
        self.product_system = product_system

    def get(self, model_type: type, _identifier: str) -> object | None:
        if model_type is olca_schema.ProductSystem:
            return self.product_system
        return None


class GraphWorkflowTests(unittest.TestCase):
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


class FakeResult:
    def __init__(self, impacts: list[object] | None = None, error: Exception | None = None) -> None:
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
        category = olca_schema.Ref(id="impact-id", name="Climate change", ref_unit="kg CO2-eq")
        result_handle = FakeResult([SimpleNamespace(impact_category=category, amount=1.25)])
        result = workflow.calculate_product_system(
            "localhost", 8080, "ps-id", "method-id", client=CalculationClient(result_handle)
        )

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["resource_released"])
        self.assertTrue(result_handle.disposed)
        self.assertEqual(result["impact_categories"][0]["id"], "impact-id")

    def test_empty_and_error_results_do_not_pass_and_release_handle(self) -> None:
        empty_handle = FakeResult([])
        empty = workflow.calculate_product_system(
            "localhost", 8080, "ps-id", "method-id", client=CalculationClient(empty_handle)
        )
        error_handle = FakeResult(error=RuntimeError("calculation failed"))
        failed = workflow.calculate_product_system(
            "localhost", 8080, "ps-id", "method-id", client=CalculationClient(error_handle)
        )

        self.assertEqual(empty["status"], "empty")
        self.assertTrue(empty["resource_released"])
        self.assertEqual(failed["status"], "failed")
        self.assertTrue(failed["resource_released"])
        self.assertIn("calculation failed", failed["error"])


if __name__ == "__main__":
    unittest.main()
