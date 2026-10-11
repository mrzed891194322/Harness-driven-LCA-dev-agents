"""Regression for run 7b272327: foreground provider references in LCI JSON."""

from harness.tools.shared.control_openlca import workflow
from harness.tools.shared.control_openlca.readonly import category_project_scope


def _proc(pid, path, exchanges):
    return {"entity_type": "Process", "id": pid, "path": path, "name": pid,
            "data": {"exchanges": exchanges}}


def _flow(fid):
    return {"entity_type": "Flow", "id": fid, "path": f"flows/{fid}.json", "name": fid,
            "data": {"@id": fid}}


def _inventory(provider_output_flow):
    return [
        _flow("F-plastic"),
        _flow("F-bottle"),
        _proc("P-bottle", "processes/a-bottle.json", [
            {"isInput": True, "flow": {"@id": "F-plastic"}, "amount": 1000.0,
             "defaultProvider": {"@id": "P-plastic"}},
            {"isInput": False, "isQuantitativeReference": True,
             "flow": {"@id": "F-bottle"}, "amount": 1000.0},
        ]),
        _proc("P-plastic", "processes/b-plastic.json", [
            {"isInput": False, "isQuantitativeReference": True,
             "flow": {"@id": provider_output_flow}, "amount": 1000.0},
        ]),
    ]


def test_foreground_provider_that_outputs_flow_passes():
    assert workflow._preflight_foreground_provider_reference_errors(_inventory("F-plastic")) == []


def test_foreground_provider_not_outputting_flow_is_reported():
    errors = workflow._preflight_foreground_provider_reference_errors(_inventory("F-bottle"))
    assert len(errors) == 1 and "P-plastic" in errors[0] and "F-plastic" in errors[0]


def test_project_scope_labels():
    assert category_project_scope(None, "LCA") == "uncategorized"
    assert category_project_scope("", "LCA") == "uncategorized"
    assert category_project_scope("LCA/sub", "LCA") == "project"
    assert category_project_scope("C:Manufacturing/22", "LCA") == "background"
