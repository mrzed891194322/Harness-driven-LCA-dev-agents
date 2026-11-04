"""run_batch.copy_result_tree must persist workflow ARTIFACT_RELS (triage/decomposition)."""

from pathlib import Path
import importlib.util
import json

REPO = Path(__file__).resolve().parents[3]
PATH = REPO / ".benchmark/scripts/run_batch.py"


def _mod():
    spec = importlib.util.spec_from_file_location("run_batch", PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _copy_in_tmp_repo(tmp_path, monkeypatch, *, workflow: str, rel: Path, payload: dict):
    m = _mod()
    repo = tmp_path / "repo"
    (repo / ".benchmark").mkdir(parents=True)
    monkeypatch.setattr(m, "REPO", repo)

    workspace = tmp_path / "workspace"
    src = workspace / rel
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    out = m.copy_result_tree(
        "pcf",
        "sub",
        "case-1",
        "run-abc",
        workspace,
        {"status": "done"},
        {"workflow": workflow},
        workflow=workflow,
    )
    return out, rel


def test_copy_result_tree_includes_triage_json(tmp_path, monkeypatch):
    rel = Path("artifacts/triage/triage.json")
    out, rel = _copy_in_tmp_repo(
        tmp_path,
        monkeypatch,
        workflow="lci-triage-01",
        rel=rel,
        payload={"items": [{"id": "x"}]},
    )
    assert (out / rel).is_file()
    data = json.loads((out / rel).read_text(encoding="utf-8"))
    assert data["items"][0]["id"] == "x"


def test_copy_result_tree_includes_decomposition_json(tmp_path, monkeypatch):
    rel = Path("artifacts/bom/decomposition.json")
    out, rel = _copy_in_tmp_repo(
        tmp_path,
        monkeypatch,
        workflow="bom-decomposition-01",
        rel=rel,
        payload={"nodes": []},
    )
    assert (out / rel).is_file()


def test_copy_result_tree_still_includes_mapping_without_duplicate(tmp_path, monkeypatch):
    m = _mod()
    repo = tmp_path / "repo"
    (repo / ".benchmark").mkdir(parents=True)
    monkeypatch.setattr(m, "REPO", repo)

    workspace = tmp_path / "workspace"
    rel = Path("artifacts/mapping/mapping.json")
    (workspace / rel).parent.mkdir(parents=True, exist_ok=True)
    (workspace / rel).write_text('{"mappings": []}\n', encoding="utf-8")

    out = m.copy_result_tree(
        "pcf",
        "mapping",
        "m-1",
        "run-1",
        workspace,
        {"status": "done"},
        {},
        workflow="lci-mapping-01",
    )
    assert (out / rel).is_file()
    assert (out / rel).read_text(encoding="utf-8").count('"mappings"') == 1
