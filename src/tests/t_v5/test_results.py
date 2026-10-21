"""v5 results view: per-node verdicts and revise rev files listed next to originals (temp dirs only)."""

import json
from pathlib import Path

from backend.v5.results import Results


def _w(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")


def test_node_verdicts_and_rev_files(tmp_path: Path) -> None:
    runs = tmp_path / "workspace/runs"
    _w(runs / "_run/manifest.json", {"status": "running", "current_node": "b",
                                     "nodes": [{"id": "b"}, {"id": "a"}]})
    _w(runs / "a/status.json", {"status": "passed"})
    _w(runs / "a/executor/submit_round_1.json", {"role": "executor", "status": "ok", "summary": "done"})
    _w(runs / "a/reviewer/submit_round_1.json", {"role": "reviewer", "verdict": "accept", "feedback": "ok"})
    _w(runs / "b/status.json", {"status": "running"})
    _w(runs / "b/executor/submit_round_2.json", {"role": "executor", "status": "ok"})
    _w(runs / "b/reviewer/submit_round_1.json", {"role": "reviewer", "verdict": "reject", "feedback": "fix x"})
    _w(runs / "b/executor/submit_round_1.json", {"role": "executor", "status": "ok"})
    _w(tmp_path / "workspace/artifacts/report/report.md", "# r")
    _w(tmp_path / "workspace/artifacts/plan/main_plan.md", "# plan")
    _w(tmp_path / "workspace/artifacts/report/report.rev1.md", "# rev1")

    out = Results(tmp_path).results()

    assert out["manifest"]["current_node"] == "b"
    rows = [(h["stage"], h["role"], h["attempt"], h["status"]) for h in out["handoffs"]]
    assert rows == [
        ("b", "executor", 1, "ok"),
        ("b", "reviewer", 1, "reject"),
        ("b", "executor", 2, "ok"),
        ("a", "executor", 1, "ok"),
        ("a", "reviewer", 1, "accept"),
    ]
    assert out["handoffs"][1]["status_reason"] == "fix x"
    assert out["handoffs"][3]["node_status"] == "passed"
    assert out["handoffs"][0]["name"] == "runs/b/executor/submit_round_1.json"
    cats = {a["path"]: a.get("category") for a in out["artifacts"]}
    assert cats["workspace/artifacts/report/report.rev1.md"] == "deliverable"
    assert cats["workspace/artifacts/report/report.md"] == "deliverable"
    assert "workspace/artifacts/plan/main_plan.md" not in cats
    # Every verdict row is readable through the file endpoint path rules.
    assert Results(tmp_path).read_result_file("workspace/" + out["handoffs"][0]["name"])["kind"] == "json"


def test_run_files_are_intermediate(tmp_path):
    from backend.v5.results import _list_workspace_artifacts
    (tmp_path / "artifacts" / "bom").mkdir(parents=True)
    (tmp_path / "artifacts" / "bom" / "bom.md").write_text("x")
    (tmp_path / "runs" / "lca-bom" / "executor").mkdir(parents=True)
    (tmp_path / "runs" / "lca-bom" / "executor" / "submit_round_1.json").write_text("{}")
    (tmp_path / "runs" / "lca-bom" / "status.json").write_text("{}")
    cats = {a["path"]: a.get("category") for a in _list_workspace_artifacts(tmp_path)}
    assert cats["workspace/artifacts/bom/bom.md"] == "deliverable"
    assert cats["workspace/runs/lca-bom/status.json"] == "intermediate"
    assert all(c for c in cats.values())
