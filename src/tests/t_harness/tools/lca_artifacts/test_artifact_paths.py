"""Checks and report read/write paths under runs/ + artifacts/."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from harness.tools.shared.lca_artifacts import checks
from harness.tools.shared.lca_artifacts.artifact_paths import stage_file
from harness.tools.shared.lca_artifacts.store import Context
from tests.support.openlca_fakes import write_product_system_fixture


def _ctx(tmp_path: Path, stage: str, attempt: int = 1, role: str = "executor") -> Context:
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "runs" / "_run").mkdir(parents=True, exist_ok=True)
    return Context(tmp_path, ws, "run-1", stage, attempt, role=role)


def _bom(path: Path, item_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "item_id": item_id,
                        "name": "物料",
                        "quantity": 1,
                        "unit": "kg",
                        "process": "制造",
                        "transport": None,
                        "geography": "CN",
                        "source_locations": ["harness/knowledge/plan/main_plan.md#L1"],
                        "extraction_status": "extracted",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_stage02_bom_current_attempt_vs_artifacts(tmp_path: Path) -> None:
    ctx02 = _ctx(tmp_path, "02-inventory-extraction")
    attempt_bom = ctx02.path("extracted-bom.json")
    _bom(attempt_bom, "attempt")
    legacy = ctx02.workspace / "outputs" / "inventory" / "extracted-bom.json"
    _bom(legacy, "legacy")
    assert stage_file(ctx02, "02-inventory-extraction", "extracted-bom.json") == attempt_bom
    assert json.loads(attempt_bom.read_text(encoding="utf-8"))["items"][0]["item_id"] == "attempt"

    ctx03 = _ctx(tmp_path, "03-dataset-mapping")
    art_bom = ctx03.workspace / "artifacts" / "extracted-bom.json"
    _bom(art_bom, "artifacts")
    assert stage_file(ctx03, "02-inventory-extraction", "extracted-bom.json") == art_bom


def test_stage03_mapping_and_lci_attempt_vs_stage04_artifacts(tmp_path: Path) -> None:
    ctx03 = _ctx(tmp_path, "03-dataset-mapping")
    write_product_system_fixture(ctx03.path("LCI"))
    (ctx03.path("LCI") / "human_readable_mapping.md").write_text("说明")
    _bom(ctx03.workspace / "artifacts" / "extracted-bom.json", "b1")
    ctx03.path("process-mapping.json").write_text(
        json.dumps({"items": [{"item_id": "b1"}]}), encoding="utf-8"
    )
    assert checks.validate(ctx03, "mapping")["ok"]

    art = ctx03.workspace / "artifacts"
    shutil.copytree(ctx03.path("LCI"), art / "LCI", dirs_exist_ok=True)
    (art / "process-mapping.json").write_text(
        ctx03.path("process-mapping.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    ctx04 = _ctx(tmp_path, "04-openlca-reporting")
    assert stage_file(ctx04, "03-dataset-mapping", "process-mapping.json") == art / "process-mapping.json"
    assert stage_file(ctx04, "03-dataset-mapping", "LCI") == art / "LCI"


def test_report_path_is_current_attempt(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, "04-openlca-reporting")
    target = ctx.path("lca_report.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# 中文\n", encoding="utf-8")
    assert checks.report_path(ctx) == target


def test_legacy_outputs_bom_ignored(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, "02-inventory-extraction")
    legacy = ctx.workspace / "outputs" / "inventory" / "extracted-bom.json"
    _bom(legacy, "legacy-only")
    attempt = stage_file(ctx, "02-inventory-extraction", "extracted-bom.json")
    assert attempt != legacy
    assert not attempt.is_file()


def test_reviewer_reads_latest_writer_including_reviser(tmp_path):
    from types import SimpleNamespace

    from harness.tools.shared.lca_artifacts.artifact_paths import STAGE_03, stage_file

    ws = tmp_path / "workspace"
    for d in ("executor-1", "reviser-2"):
        (ws / "runs" / STAGE_03 / d).mkdir(parents=True)
    ctx = SimpleNamespace(
        workspace=ws, stage=STAGE_03, role="reviewer", attempt=3, safe=lambda p: p
    )
    assert stage_file(ctx, STAGE_03, "process-mapping.json") == (
        ws / "runs" / STAGE_03 / "reviser-2" / "process-mapping.json"
    )
    ctx.attempt = 1
    assert stage_file(ctx, STAGE_03, "process-mapping.json") == (
        ws / "runs" / STAGE_03 / "executor-1" / "process-mapping.json"
    )
