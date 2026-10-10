"""LCI import: mass-transport (t*km) unit reconciliation with provider units."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from harness.tools.shared.control_openlca import workflow

PROV, FLOW = "prov-1", "flow-1"


def _inventory(unit_name, amount=19500.0):
    exchange = {
        "@type": "Exchange",
        "isInput": True,
        "amount": amount,
        "flow": {"@type": "Flow", "@id": FLOW, "name": "transport, lorry"},
        "defaultProvider": {"@type": "Process", "@id": PROV},
    }
    if unit_name is not None:
        exchange["unit"] = {"@type": "Unit", "name": unit_name}
    return [
        {
            "entity_type": "Process",
            "id": "p1",
            "path": "processes/p1.json",
            "data": {"exchanges": [exchange]},
        }
    ]


def _checks(unit="t*km"):
    return [
        {
            "provider_id": PROV,
            "flow_id": FLOW,
            "provider_unit": {"id": "u-tkm", "name": unit, "flow_property": "x"},
        }
    ]


@pytest.mark.parametrize("name", ["kg*km", "kg·km", "kgkm", "KG*KM"])
def test_kgkm_converted_to_tkm_with_note(name):
    inv = _inventory(name)
    conversions, errors = workflow._transport_unit_pass(inv, _checks())
    assert errors == []
    ex = inv[0]["data"]["exchanges"][0]
    assert ex["amount"] == pytest.approx(19.5)
    assert ex["unit"] == {"@type": "Unit", "name": "t*km", "@id": "u-tkm"}
    assert len(conversions) == 1
    c = conversions[0]
    assert c["original_amount"] == 19500.0 and c["factor"] == pytest.approx(0.001)
    assert "converted" in c["note"]


def test_same_unit_untouched():
    inv = _inventory("t*km", 19.5)
    conversions, errors = workflow._transport_unit_pass(inv, _checks())
    assert conversions == [] and errors == []
    assert inv[0]["data"]["exchanges"][0]["amount"] == 19.5


@pytest.mark.parametrize(
    "name, needle", [(None, "unit missing"), ("kg", "incompatible")]
)
def test_missing_or_incompatible_unit_rejected(name, needle):
    inv = _inventory(name)
    conversions, errors = workflow._transport_unit_pass(inv, _checks())
    assert conversions == []
    assert errors and needle in errors[0]
    assert inv[0]["data"]["exchanges"][0]["amount"] == 19500.0


def test_transport_unit_against_non_transport_provider_rejected():
    inv = _inventory("kg*km")
    _conv, errors = workflow._transport_unit_pass(inv, _checks(unit="kg"))
    assert errors and "mass*distance" in errors[0]


def test_provider_output_unit_reads_reference_exchange():
    provider = SimpleNamespace(
        exchanges=[
            SimpleNamespace(is_input=True, flow=SimpleNamespace(id=FLOW)),
            SimpleNamespace(
                is_input=False,
                flow=SimpleNamespace(id=FLOW),
                unit=SimpleNamespace(id="u", name="t*km"),
                flow_property=SimpleNamespace(name="Goods transport (mass*distance)"),
            ),
        ]
    )
    assert workflow._provider_output_unit(provider, FLOW)["name"] == "t*km"
    assert workflow._provider_output_unit(provider, "other") is None
