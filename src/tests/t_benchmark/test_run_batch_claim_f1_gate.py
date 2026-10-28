"""run_batch: mapping/triage must not emit claim_f1 no_artifact."""

from pathlib import Path
import importlib.util

REPO = Path(__file__).resolve().parents[3]
PATH = REPO / ".benchmark/scripts/run_batch.py"


def _mod():
    spec = importlib.util.spec_from_file_location("run_batch", PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_uses_claim_f1_false_for_mapping_triage_decomp():
    m = _mod()
    assert m.uses_claim_f1("lci-mapping-01") is False
    assert m.uses_claim_f1("lci-mapping-03") is False
    assert m.uses_claim_f1("lci-triage-01") is False
    assert m.uses_claim_f1("lci-triage-04") is False
    assert m.uses_claim_f1("bom-decomposition-01") is False


def test_uses_claim_f1_true_for_extract_abstention():
    m = _mod()
    assert m.uses_claim_f1("bom-extract-01") is True
    assert m.uses_claim_f1("bom-extract-03") is True
    assert m.uses_claim_f1("bom-claims-03") is True  # legacy / unknown claim suites


def test_mapping_row_notes_have_no_claim_no_artifact():
    """Simulate the notes assembly contract: claim F1 tag only when uses_claim_f1."""
    m = _mod()
    for wf in ("lci-mapping-01", "lci-triage-01"):
        assert m.uses_claim_f1(wf) is False
        # What used to happen: f1 = zero_f1_scores(..., reason="no_artifact")
        # → notes "F1=0.000(no_artifact)" even with mapping.json present.
        # Gate: callers must skip claim F1 entirely for these workflows.
        fake_f1 = {"f1": 0.0, "reason": "no_artifact"}
        notes = []
        if m.uses_claim_f1(wf):
            notes.append(f"F1={fake_f1['f1']:.3f}({fake_f1['reason']})")
        assert "no_artifact" not in ";".join(notes)
