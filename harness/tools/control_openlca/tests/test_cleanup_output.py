from __future__ import annotations

import unittest
from types import SimpleNamespace

import olca_schema

from harness.tools.control_openlca.utils import cleanup


class FakeCleanupClient:
    def __init__(
        self,
        descriptors: dict[type, list[object]] | None = None,
        errors: dict[type, Exception] | None = None,
    ) -> None:
        self.descriptors = descriptors or {}
        self.errors = errors or {}
        self.requested_types: list[type] = []
        self.delete_calls: list[object] = []

    def get_descriptors(self, model_type: type) -> list[object]:
        self.requested_types.append(model_type)
        if model_type in self.errors:
            raise self.errors[model_type]
        return list(self.descriptors.get(model_type, []))

    def delete(self, reference: object) -> None:
        self.delete_calls.append(reference)


def descriptor(
    entity_id: str,
    name: str,
    category: str | None,
) -> SimpleNamespace:
    reference = SimpleNamespace(id=entity_id, name=name)
    return SimpleNamespace(
        id=entity_id,
        name=name,
        category=category,
        to_ref=lambda: reference,
    )


class CleanupOutputTests(unittest.TestCase):
    def test_collect_entities_fails_closed_on_partial_descriptor_error(self) -> None:
        client = FakeCleanupClient(
            descriptors={
                olca_schema.ProductSystem: [
                    descriptor("system-1", "System", "project-a"),
                ],
            },
            errors={
                olca_schema.Process: TimeoutError("descriptor timeout"),
            },
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "Failed to get Process descriptors; cleanup scope is incomplete",
        ):
            cleanup.collect_entities(
                client,
                "project-a",
                [
                    olca_schema.ProductSystem,
                    olca_schema.Process,
                    olca_schema.Flow,
                ],
            )

        self.assertEqual(
            client.requested_types,
            [olca_schema.ProductSystem, olca_schema.Process],
        )
        self.assertEqual(client.delete_calls, [])

    def test_collect_entities_allows_complete_empty_scan(self) -> None:
        client = FakeCleanupClient()
        model_types = [
            olca_schema.ProductSystem,
            olca_schema.Process,
            olca_schema.Flow,
        ]

        entities = cleanup.collect_entities(client, "project-a", model_types)

        self.assertEqual(entities, [])
        self.assertEqual(client.requested_types, model_types)

    def test_collect_entities_limits_scope_to_project_category(self) -> None:
        exact = descriptor("process-1", "Exact", "project-a")
        nested = descriptor("process-2", "Nested", "project-a/subcategory")
        unrelated = descriptor("process-3", "Other", "project-b")
        prefix_only = descriptor("process-4", "Prefix", "project-ab")
        client = FakeCleanupClient(
            descriptors={
                olca_schema.Process: [exact, nested, unrelated, prefix_only],
            }
        )

        entities = cleanup.collect_entities(
            client,
            "project-a",
            [olca_schema.Process],
        )

        self.assertEqual(
            [(model_type, item.id) for model_type, item in entities],
            [
                (olca_schema.Process, "process-1"),
                (olca_schema.Process, "process-2"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
