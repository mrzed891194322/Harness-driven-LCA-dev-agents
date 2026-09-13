"""Shared fakes and fixtures for control_openlca offline tests."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace

import olca_schema

from harness.tools.control_openlca.utils import workflow


class FakeClient:
    def __init__(
        self,
        descriptors: list[object] | None = None,
        error: Exception | None = None,
        *,
        entities: dict[tuple[type, str], object] | None = None,
        providers: Sequence[object] | None = None,
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
        return list(self.providers)


FLOW_ID = "11111111-1111-4111-8111-111111111111"
PROCESS_ID = "22222222-2222-4222-8222-222222222222"
PRODUCT_SYSTEM_ID = "33333333-3333-4333-8333-333333333333"
GENERATED_SYSTEM_ID = "44444444-4444-4444-8444-444444444444"
PROVIDER_ID = "55555555-5555-4555-8555-555555555555"


def run_import(
    root: Path,
    client: FakeImportClient,
    category: str = "project-a",
    database: str = "isolated-db",
    operation_dir: Path | None = None,
) -> dict:
    return workflow.import_lci(
        "localhost",
        8080,
        root,
        category,
        database_name=database,
        client=client,
        operation_dir=operation_dir,
    )


class FakeDescriptor:
    def __init__(self, entity_id: str, name: str, category: str | None = None) -> None:
        self.id = entity_id
        self.name = name
        self.category = category

    def to_ref(self) -> SimpleNamespace:
        return SimpleNamespace(id=self.id, name=self.name)


class FakeImportClient:
    def __init__(
        self, descriptors: dict[str, list[FakeDescriptor]] | None = None
    ) -> None:
        self.descriptors = descriptors or {}
        self.put_calls: list[object] = []
        self.delete_calls: list[object] = []
        self.fail_put = False
        self.put_error: Exception | None = None
        self.fail_put_names: set[str] = set()
        self.fail_delete_ids: set[str] = set()
        self.fail_create_product_system = False
        self.create_product_system_error: Exception | None = None
        self.query_error: Exception | None = None
        self.create_product_system_calls: list[tuple[object, object]] = []
        self.entities: dict[tuple[type, str], object] = {}
        self.close_calls = 0

    def get_descriptors(self, model_type: type) -> list[FakeDescriptor]:
        if self.query_error is not None:
            raise self.query_error
        return list(self.descriptors.get(model_type.__name__, []))

    def put(self, entity: object) -> SimpleNamespace | None:
        self.put_calls.append(entity)
        if self.put_error is not None:
            raise self.put_error
        if self.fail_put or getattr(entity, "name", None) in self.fail_put_names:
            return None
        entity_type = type(entity).__name__
        self.descriptors.setdefault(entity_type, []).append(
            FakeDescriptor(
                str(getattr(entity, "id", "") or ""),
                str(getattr(entity, "name", "") or ""),
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
        if self.create_product_system_error is not None:
            raise self.create_product_system_error
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

    def close(self) -> None:
        self.close_calls += 1


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
                "@context": workflow.JSON_LD_CONTEXT,
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
                "@context": workflow.JSON_LD_CONTEXT,
                "@type": "Process",
                "@id": PROCESS_ID,
                "name": "P01 Foreground process",
                "exchanges": [
                    {
                        "@type": "Exchange",
                        "flow": {"@type": "Flow", "@id": FLOW_ID},
                        "isInput": False,
                        "isQuantitativeReference": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (product_systems / "ps01-test.json").write_text(
        json.dumps(
            {
                "@context": workflow.JSON_LD_CONTEXT,
                "@type": "ProductSystem",
                "@id": PRODUCT_SYSTEM_ID,
                "name": "PS01 Test product system",
                "description": "Preserve this metadata",
                "refProcess": {"@type": "Process", "@id": PROCESS_ID},
                "targetAmount": 1065.0,
                "linkingMode": "auto",
                "preferDefaultProviders": True,
                "expectedProcessIds": [PROCESS_ID],
            }
        ),
        encoding="utf-8",
    )


def write_linked_auto_product_system_fixture(root: Path) -> None:
    write_product_system_fixture(root)
    processes = root / "processes"
    consumer_path = processes / "p01-test.json"
    consumer = json.loads(consumer_path.read_text(encoding="utf-8"))
    consumer["exchanges"] = [
        {
            "@type": "Exchange",
            "flow": {"@type": "Flow", "@id": FLOW_ID},
            "isInput": False,
            "isQuantitativeReference": True,
        },
        {
            "@type": "Exchange",
            "flow": {"@type": "Flow", "@id": FLOW_ID},
            "isInput": True,
            "defaultProvider": {
                "@type": "Process",
                "@id": PROVIDER_ID,
            },
        },
    ]
    consumer_path.write_text(json.dumps(consumer), encoding="utf-8")
    (processes / "p02-provider.json").write_text(
        json.dumps(
            {
                "@context": workflow.JSON_LD_CONTEXT,
                "@type": "Process",
                "@id": PROVIDER_ID,
                "name": "P02 Scenario provider",
                "exchanges": [
                    {
                        "@type": "Exchange",
                        "flow": {"@type": "Flow", "@id": FLOW_ID},
                        "isInput": False,
                        "isQuantitativeReference": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    product_systems = root / "product_systems"
    (product_systems / "ps01-test.json").write_text(
        json.dumps(
            {
                "@context": workflow.JSON_LD_CONTEXT,
                "@type": "ProductSystem",
                "@id": PRODUCT_SYSTEM_ID,
                "name": "PS01 Auto-linked product system",
                "refProcess": {"@type": "Process", "@id": PROCESS_ID},
                "linkingMode": "auto",
                "preferDefaultProviders": True,
                "expectedProcessIds": [PROCESS_ID, PROVIDER_ID],
            }
        ),
        encoding="utf-8",
    )
