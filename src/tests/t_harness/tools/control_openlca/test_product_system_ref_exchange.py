"""Incomplete ProductSystem refExchange stubs must not block generated reference flow."""

from __future__ import annotations

from types import SimpleNamespace

import olca_schema
import pytest

from harness.tools.shared.control_openlca import importer as imp
from harness.tools.shared.control_openlca.lci_inventory import _lci_semantic_errors


def _generated_ps() -> olca_schema.ProductSystem:
    return olca_schema.ProductSystem(
        id="gen-ps",
        name="generated",
        ref_process=olca_schema.Ref(id="proc-1", name="P"),
        ref_exchange=olca_schema.ExchangeRef(internal_id=42),
        processes=[olca_schema.Ref(id="proc-1")],
        process_links=[],
        target_amount=1.0,
    )


def test_stub_ref_exchange_not_usable():
    stub = olca_schema.ProductSystem.from_dict(
        {
            "@type": "ProductSystem",
            "@id": "ps-1",
            "name": "Case",
            "refExchange": {
                "@type": "Exchange",
                "@id": "a1b2c3d0-4101-4000-8000-000000000006",
            },
        }
    ).ref_exchange
    assert stub is not None
    assert getattr(stub, "internal_id", None) is None
    assert not imp._product_system_ref_exchange_usable(stub)
    assert imp._product_system_ref_exchange_usable(
        olca_schema.ExchangeRef(internal_id=7)
    )
    assert not imp._product_system_ref_exchange_usable(
        olca_schema.Exchange(internal_id=7, flow=None, is_input=False, amount=1.0)
    )
    assert imp._product_system_ref_exchange_usable(
        olca_schema.Exchange(
            internal_id=7,
            flow=olca_schema.Ref(id="flow-1"),
            is_input=False,
            amount=1.0,
        )
    )


def test_apply_generated_overwrites_incomplete_stub():
    entity = olca_schema.ProductSystem.from_dict(
        {
            "@type": "ProductSystem",
            "@id": "ps-1",
            "name": "Case",
            "refProcess": {"@type": "Process", "@id": "proc-1"},
            "refExchange": {
                "@type": "Exchange",
                "@id": "a1b2c3d0-4101-4000-8000-000000000006",
            },
            "linkingMode": "auto",
            "preferDefaultProviders": True,
        }
    )
    generated = _generated_ps()
    assert not imp._product_system_ref_exchange_usable(entity.ref_exchange)

    imp._apply_generated_product_system_fields(entity, generated)

    assert imp._product_system_ref_exchange_usable(entity.ref_exchange)
    assert getattr(entity.ref_exchange, "internal_id", None) == 42
    assert entity.processes == generated.processes
    assert entity.target_amount == 1.0


def test_apply_keeps_usable_existing_ref_exchange():
    entity = olca_schema.ProductSystem(
        id="ps-1",
        name="Case",
        ref_exchange=olca_schema.ExchangeRef(internal_id=99),
        ref_process=olca_schema.Ref(id="proc-keep"),
    )
    generated = _generated_ps()
    imp._apply_generated_product_system_fields(entity, generated)
    assert getattr(entity.ref_exchange, "internal_id", None) == 99
    assert getattr(entity.ref_process, "id", None) == "proc-keep"
    assert entity.processes == generated.processes


def test_auto_inventory_rejects_incomplete_ref_exchange():
    inventory = [
        {
            "path": "flows/f.json",
            "entity_type": "Flow",
            "id": "flow-1",
            "name": "F",
            "data": {
                "@type": "Flow",
                "@id": "flow-1",
                "name": "F",
                "flowType": "PRODUCT_FLOW",
            },
            "sha256": "a",
        },
        {
            "path": "processes/p.json",
            "entity_type": "Process",
            "id": "proc-1",
            "name": "P",
            "data": {
                "@type": "Process",
                "@id": "proc-1",
                "name": "P",
                "exchanges": [
                    {
                        "isInput": False,
                        "isQuantitativeReference": True,
                        "amount": 1.0,
                        "flow": {"@type": "Flow", "@id": "flow-1"},
                    }
                ],
            },
            "sha256": "b",
        },
        {
            "path": "product_systems/case-1.json",
            "entity_type": "ProductSystem",
            "id": "ps-1",
            "name": "Case",
            "data": {
                "@type": "ProductSystem",
                "@id": "ps-1",
                "name": "Case",
                "linkingMode": "auto",
                "preferDefaultProviders": True,
                "refProcess": {"@type": "Process", "@id": "proc-1"},
                "expectedProcessIds": ["proc-1"],
                "refExchange": {
                    "@type": "Exchange",
                    "@id": "a1b2c3d0-4101-4000-8000-000000000006",
                },
            },
            "sha256": "c",
        },
    ]
    errors = _lci_semantic_errors(inventory)
    assert any("incomplete refExchange" in err for err in errors)


def test_auto_put_raises_when_readback_ref_exchange_invalid(monkeypatch):
    entity = olca_schema.ProductSystem(
        id="ps-declared",
        name="Case",
        ref_process=olca_schema.Ref(id="proc-1"),
    )
    generated = _generated_ps()
    generated.id = "ps-generated-temp"

    class FakeClient:
        def create_product_system(self, ref_process, config):
            return SimpleNamespace(id=generated.id)

        def get(self, model_type, entity_id):
            if entity_id == generated.id:
                return generated
            if entity_id == "ps-declared":
                # Simulate openLCA keeping empty reference flow after bad put.
                return olca_schema.ProductSystem(
                    id="ps-declared",
                    name="Case",
                    ref_exchange=olca_schema.ExchangeRef(),
                )
            return None

        def put(self, obj):
            return SimpleNamespace(id=getattr(obj, "id", None))

        def delete(self, ref):
            return None

    monkeypatch.setattr(imp, "ipc_read_scope", lambda _sec: _NullCtx())
    monkeypatch.setattr(imp, "product_system_read_sec", lambda: 1.0)

    with pytest.raises(RuntimeError, match="ref_exchange is missing or invalid"):
        imp._put_product_system(
            FakeClient(),
            entity,
            {
                "linkingMode": "auto",
                "preferDefaultProviders": True,
                "refProcess": {"@id": "proc-1"},
                "expectedProcessIds": ["proc-1"],
            },
            inventory=[
                {
                    "entity_type": "Process",
                    "id": "proc-1",
                    "name": "P",
                    "data": {"exchanges": []},
                }
            ],
            target_category="proj",
        )


class _NullCtx:
    def __enter__(self):
        return None

    def __exit__(self, *args):
        return False
