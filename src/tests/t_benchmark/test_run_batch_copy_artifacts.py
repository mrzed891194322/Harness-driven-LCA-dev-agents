"""run_batch.copy_result_tree persists deliverables and triage decision evidence."""

from pathlib import Path
import importlib.util
import json

import pytest

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


@pytest.mark.parametrize(
    ("workflow", "has_checklist"),
    [("lci-triage-04", True), ("lci-triage-04", False), ("lci-triage-01", True)],
)
def test_copy_result_tree_promotes_triage_04_checklist(
    tmp_path, monkeypatch, workflow, has_checklist
):
    workspace = tmp_path / "workspace"
    source = workspace / "runs/lci-triage-04/executor/checklist.json"
    checklist = {
        "axis_a": {
            "candidates": ["listed activity"],
            "reasonable_direct_match": "yes",
            "reason": "候选覆盖整体",
        },
        "axis_b": {"must_decompose_first": "no", "reason": "无实质拆分需求"},
        "decision_preview": True,
    }
    if has_checklist:
        source.parent.mkdir(parents=True)
        source.write_text(json.dumps(checklist, ensure_ascii=False) + "\n", encoding="utf-8")
    payload = {"should_map": True, "rationale": "Direct match; no decomposition needed."}
    out, artifact_rel = _copy_in_tmp_repo(
        tmp_path,
        monkeypatch,
        workflow=workflow,
        rel=Path("artifacts/triage/triage.json"),
        payload=payload,
    )
    dest = out / "runs/_run/notes/lci-triage-04/executor/checklist.json"
    if workflow == "lci-triage-04" and has_checklist:
        assert dest.read_bytes() == source.read_bytes()
        assert json.loads(dest.read_text(encoding="utf-8")) == checklist
        assert not (out / "runs/lci-triage-04/executor/checklist.json").exists()
    else:
        assert not dest.exists()
    assert json.loads((out / artifact_rel).read_text(encoding="utf-8")) == payload
    assert not (out / "runs/_run/artifacts/triage/triage.json").exists()


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
