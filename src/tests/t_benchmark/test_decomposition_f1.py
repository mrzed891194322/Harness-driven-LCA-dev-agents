from pathlib import Path
import importlib.util

REPO = Path(__file__).resolve().parents[3]
PATH = REPO / ".benchmark/bom/scorers/decomposition_f1.py"


def _mod():
    spec = importlib.util.spec_from_file_location("decomposition_f1", PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_norm_match_and_zero():
    m = _mod()
    s = m.score_decomposition(
        {"components": ["Aluminium Scrap - pre consumer", "Primary Aluminium"]},
        {"components": ["aluminium scrap - pre consumer", "Primary Aluminium", "Extra"]},
    )
    assert s["matched"] == 2 and s["f1"] == 0.8
    z = m.zero_pred_scores({"components": ["a"]}, reason="no_submit")
    assert z["f1"] == 0.0 and z["reason"] == "no_submit"
