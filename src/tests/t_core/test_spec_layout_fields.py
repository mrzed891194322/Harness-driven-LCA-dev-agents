"""Stage spec v2: handoff|deliverable kinds and from: inputs (layout migration)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.workflow.spec.loader import load_stage_spec

REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "stage",
    ["01-intake-gate", "02-inventory-extraction", "03-dataset-mapping", "04-openlca-reporting"],
)
def test_repo_stage_specs_load_with_artifact_kinds(stage: str) -> None:
    rel = f"harness/specs/{stage}/spec.yaml"
    spec = load_stage_spec(REPO / rel, project_root=REPO, relative=rel)
    for item in spec.inputs:
        if item.artifact_kind is not None:
            assert item.artifact_kind in {"handoff", "deliverable"}
    for d in spec.deliverables:
        assert d.artifact_kind in {"handoff", "deliverable", None}


def test_stage_03_input_from_ref() -> None:
    rel = "harness/specs/03-dataset-mapping/spec.yaml"
    spec = load_stage_spec(REPO / rel, project_root=REPO, relative=rel)
    bom = next(i for i in spec.inputs if i.from_ref)
    assert bom.from_ref == "02-inventory-extraction/extracted-bom.json"


def test_stage_04_declares_calculation_plan_and_results() -> None:
    rel = "harness/specs/04-openlca-reporting/spec.yaml"
    spec = load_stage_spec(REPO / rel, project_root=REPO, relative=rel)
    names = {d.name for d in spec.deliverables}
    assert {"calculation-plan", "results", "lca_report"} <= names
