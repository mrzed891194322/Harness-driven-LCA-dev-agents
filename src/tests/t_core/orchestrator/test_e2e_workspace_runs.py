"""End-to-end workspace runs layout (scripted agent, no real openLCA)."""

from __future__ import annotations

import json
from pathlib import Path

from backend.core.workflow.workspace.index import register_attempt
from backend.services.openlca_attempt_cleanup import maybe_cleanup_before_openlca_write
from unittest.mock import patch

STAGES = (
    "01-intake-gate",
    "02-inventory-extraction",
    "03-dataset-mapping",
    "04-openlca-reporting",
)
DELIVERABLE_NAMES = frozenset(
    {
        "lca_report.md",
        "calculation-plan.json",
        "results.json",
        "extracted-bom.json",
        "extracted-bom.md",
        "process-mapping.json",
        "human_readable_mapping.md",
    }
)


def _seed_stage_attempt(ws: Path, stage: str, role: str, attempt: int) -> Path:
    root = ws / "runs" / stage / f"{role}-{attempt}"
    root.mkdir(parents=True, exist_ok=True)
    (root / "handoff.json").write_text(
        json.dumps({"schema_version": 1, "status": "passed", "stage": stage}),
        encoding="utf-8",
    )
    register_attempt(ws, stage, role, attempt, "run-e2e", origin="whole-lca")
    return root


def test_runs_layout_attempts_accepted_and_artifacts(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    artifacts = ws / "artifacts"
    artifacts.mkdir(parents=True)
    for stage in STAGES:
        _seed_stage_attempt(ws, stage, "executor", 1)
        _seed_stage_attempt(ws, stage, "reviewer", 1)
        doc_path = ws / "runs" / stage / "attempts.json"
        doc = json.loads(doc_path.read_text(encoding="utf-8"))
        assert doc.get("stage") == stage
        assert isinstance(doc.get("attempts"), list)
        for row in doc["attempts"]:
            assert "dir" in row and "role" in row and "attempt" in row
        accepted_path = ws / "runs" / stage / "accepted.json"
        accepted_path.write_text(
            json.dumps(
                {
                    "stage": stage,
                    "executor": f"runs/{stage}/executor-1",
                    "reviewer": f"runs/{stage}/reviewer-1",
                    "accepted_at": "2026-01-01T00:00:00Z",
                    "fingerprint": "deadbeef",
                }
            ),
            encoding="utf-8",
        )
    (artifacts / "lca_report.md").write_text("# report\n", encoding="utf-8")
    (artifacts / "results.json").write_text(
        json.dumps({"cases": [], "schema": "whole-lca/results"}),
        encoding="utf-8",
    )
    for name in DELIVERABLE_NAMES:
        if name in {"lca_report.md", "results.json"}:
            continue
        target = artifacts / name
        if name == "LCI":
            target.mkdir(exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("{}", encoding="utf-8")
    allowed = {p.name for p in artifacts.iterdir()}
    assert "lca_report.md" in allowed and "results.json" in allowed


def test_04_second_attempt_records_openlca_deleted(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    stage = "04-openlca-reporting"
    journal1 = ws / "runs" / stage / "executor-1" / "import-operations" / "operations"
    journal1.mkdir(parents=True)
    (journal1 / "1.json").write_text(
        json.dumps({"entities": [{"@type": "Process", "@id": "old-p"}]}),
        encoding="utf-8",
    )
    register_attempt(ws, stage, "executor", 1, "r1")
    register_attempt(ws, stage, "executor", 2, "r2")

    class Ent:
        name = "old-p"
        category = "202606-harness-agent-LCA/x"

        def to_ref(self):
            return self

    class Client:
        def get(self, *_a):
            return Ent()

        def delete(self, _r):
            return None

    with patch(
        "backend.services.openlca_attempt_cleanup.connect_ipc",
        return_value=Client(),
    ), patch(
        "backend.services.openlca_attempt_cleanup.close_ipc_client",
        lambda _c: None,
    ), patch(
        "backend.services.openlca_attempt_cleanup.openlca_endpoint",
        return_value=("127.0.0.1", 9),
    ):
        maybe_cleanup_before_openlca_write(
            tmp_path, ws, stage_id=stage, role="executor", attempt=2
        )
    doc = json.loads((ws / "runs" / stage / "attempts.json").read_text(encoding="utf-8"))
    row = next(r for r in doc["attempts"] if r["attempt"] == 2)
    assert row.get("openlca_deleted")
