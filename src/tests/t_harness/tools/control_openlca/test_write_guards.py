"""Fail-closed import guard and category re-check in cleanup delete."""

from __future__ import annotations

from types import SimpleNamespace

import olca_schema

from harness.tools.shared.control_openlca.cleanup import delete_entities
from harness.tools.shared.control_openlca.importer import (
    _outside_project_import_refusal,
)

PROJECT = "202606-harness-agent-LCA"


class _Client:
    def __init__(self, store=None, raise_on_get=False):
        self.store = store or {}
        self.raise_on_get = raise_on_get
        self.deleted: list[str] = []

    def get(self, model_type, entity_id):
        # import guard (not cleanup) still uses a full get
        return self.get_descriptor(model_type, entity_id)

    def get_descriptor(self, model_type, entity_id):
        if self.raise_on_get:
            raise RuntimeError("ipc down")
        return self.store.get(entity_id)

    def delete(self, ref):
        self.deleted.append(ref.id)


def _desc(entity_id, name="x"):
    return SimpleNamespace(
        id=entity_id, name=name, to_ref=lambda: SimpleNamespace(id=entity_id)
    )


def test_import_guard_refuses_when_get_raises():
    item = {"entity_type": "Flow", "id": "f1"}
    refusal = _outside_project_import_refusal(_Client(raise_on_get=True), item, PROJECT)
    assert refusal is not None and "拒绝写入" in refusal


def test_import_guard_allows_not_found():
    item = {"entity_type": "Flow", "id": "f1"}
    assert _outside_project_import_refusal(_Client(), item, PROJECT) is None


def test_delete_skips_foreign_and_deletes_project_entities():
    store = {
        "own": SimpleNamespace(id="own", category=f"{PROJECT}/flows"),
        "foreign": SimpleNamespace(id="foreign", category="Elementary flows/air"),
        "unit": SimpleNamespace(id="unit", category="Technical unit groups"),
    }
    client = _Client(store)
    entities = [
        (olca_schema.Flow, _desc("own")),
        (olca_schema.Flow, _desc("foreign")),
        (olca_schema.Flow, _desc("missing")),
        (olca_schema.UnitGroup, _desc("unit")),
    ]
    count, errors = delete_entities(
        client,
        entities,
        [olca_schema.Flow, olca_schema.UnitGroup],
        project_name=PROJECT,
    )
    assert client.deleted == ["own"]
    assert count == 1
    assert len(errors) == 2


def test_delete_skips_when_lookup_errors():
    client = _Client(raise_on_get=True)
    count, errors = delete_entities(
        client, [(olca_schema.Flow, _desc("own"))], [olca_schema.Flow],
        project_name=PROJECT,
    )
    assert count == 0 and client.deleted == [] and errors
