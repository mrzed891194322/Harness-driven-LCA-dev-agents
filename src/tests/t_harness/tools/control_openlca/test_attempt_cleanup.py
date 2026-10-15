from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.tools.shared.control_openlca.attempt_cleanup import (
    _salvage_entity_ids,
    cleanup_prior_attempt_imports,
    journal_entity_ids,
    strict_project_category,
    validate_target_category,
)

STAGE = "04-openlca-reporting"
PROJECT = "202606-harness-agent-LCA"


def _journal(ws: Path, role: str, attempt: int) -> Path:
    return ws / "runs" / STAGE / f"{role}-{attempt}" / "import-operations"


def _write_ops(journal: Path, entities: list[dict]) -> None:
    ops = journal / "operations"
    ops.mkdir(parents=True, exist_ok=True)
    (ops / "1.json").write_text(json.dumps({"entities": entities}), encoding="utf-8")


def _attempts_doc(ws: Path, rows: list[dict]) -> None:
    path = ws / "runs" / STAGE / "attempts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"stage": STAGE, "attempts": rows}, ensure_ascii=False),
        encoding="utf-8",
    )


def _run_cleanup(
    ws: Path,
    *,
    current_role: str = "executor",
    current_attempt: int = 2,
    accepted: dict | None = None,
    fetch=None,
    delete=None,
):
    removed: list[tuple[str, str, str]] = []

    def default_fetch(entity_type: str, entity_id: str):
        return {
            "name": entity_id,
            "category": f"{PROJECT}/x",
        }

    def default_delete(entity_type: str, entity_id: str, name: str) -> None:
        removed.append((entity_type, entity_id, name))

    deleted, skipped = cleanup_prior_attempt_imports(
        ws,
        stage_id=STAGE,
        current_role=current_role,
        current_attempt=current_attempt,
        accepted=accepted or {},
        fetch_entity=fetch or default_fetch,
        delete_entity=delete or default_delete,
    )
    return deleted, skipped, removed


def test_cleanup_orders_product_system_before_process_and_flow(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    _write_ops(
        _journal(ws, "executor", 1),
        [
            {"@type": "Flow", "@id": "f1"},
            {"@type": "Process", "@id": "p1"},
            {"@type": "ProductSystem", "@id": "ps1"},
        ],
    )
    _attempts_doc(
        ws,
        [
            {"dir": f"runs/{STAGE}/executor-1", "role": "executor", "attempt": 1},
            {"dir": f"runs/{STAGE}/executor-2", "role": "executor", "attempt": 2},
        ],
    )
    _journal(ws, "executor", 2).mkdir(parents=True)
    deleted, _, _ = _run_cleanup(ws)
    assert [row["type"] for row in deleted] == ["ProductSystem", "Process", "Flow"]


def test_cleanup_only_deletes_ids_from_logs(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    _write_ops(_journal(ws, "executor", 1), [{"@type": "Process", "@id": "logged"}])
    _attempts_doc(
        ws,
        [
            {"dir": f"runs/{STAGE}/executor-1", "role": "executor", "attempt": 1},
            {"dir": f"runs/{STAGE}/executor-2", "role": "executor", "attempt": 2},
        ],
    )
    deleted, _, removed = _run_cleanup(ws)
    assert removed == [("Process", "logged", "logged")]
    assert deleted[0]["id"] == "logged"


def test_overlap_with_current_attempt_skipped(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    _write_ops(_journal(ws, "executor", 1), [{"@type": "Process", "@id": "shared"}])
    _write_ops(_journal(ws, "executor", 2), [{"@type": "Process", "@id": "shared"}])
    _attempts_doc(
        ws,
        [
            {"dir": f"runs/{STAGE}/executor-1", "role": "executor", "attempt": 1},
            {"dir": f"runs/{STAGE}/executor-2", "role": "executor", "attempt": 2},
        ],
    )
    _, skipped, removed = _run_cleanup(ws)
    assert not removed
    assert any(s.get("reason") == "overlap" and s["id"] == "shared" for s in skipped)


def test_overlap_with_accepted_attempt_skipped(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    _write_ops(_journal(ws, "executor", 1), [{"@type": "Process", "@id": "shared"}])
    _write_ops(_journal(ws, "executor", 2), [{"@type": "Process", "@id": "shared"}])
    _write_ops(_journal(ws, "executor", 3), [{"@type": "Process", "@id": "shared"}])
    _attempts_doc(
        ws,
        [
            {"dir": f"runs/{STAGE}/executor-1", "role": "executor", "attempt": 1},
            {"dir": f"runs/{STAGE}/executor-2", "role": "executor", "attempt": 2},
            {"dir": f"runs/{STAGE}/executor-3", "role": "executor", "attempt": 3},
        ],
    )
    accepted = {"executor": f"runs/{STAGE}/executor-2"}
    _, skipped, removed = _run_cleanup(ws, current_attempt=3, accepted=accepted)
    assert not any(r[1] == "shared" for r in removed)
    assert any(s["id"] == "shared" and s["reason"] == "overlap" for s in skipped)


def test_accepted_writer_attempt_never_deleted(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    _write_ops(_journal(ws, "executor", 2), [{"@type": "Process", "@id": "acc"}])
    _write_ops(_journal(ws, "executor", 1), [{"@type": "Process", "@id": "old"}])
    _attempts_doc(
        ws,
        [
            {"dir": f"runs/{STAGE}/executor-1", "role": "executor", "attempt": 1},
            {"dir": f"runs/{STAGE}/executor-2", "role": "executor", "attempt": 2},
            {"dir": f"runs/{STAGE}/executor-3", "role": "executor", "attempt": 3},
        ],
    )
    accepted = {"executor": f"runs/{STAGE}/executor-2"}
    deleted, _, removed = _run_cleanup(ws, current_attempt=3, accepted=accepted)
    assert not any(r[1] == "acc" for r in removed)
    assert any(d["id"] == "old" for d in deleted)


def test_interrupted_attempt_without_review_is_deleted(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    _write_ops(_journal(ws, "executor", 1), [{"@type": "ProductSystem", "@id": "ps"}])
    _attempts_doc(
        ws,
        [
            {
                "dir": f"runs/{STAGE}/executor-1",
                "role": "executor",
                "attempt": 1,
                "status": "running",
            },
            {"dir": f"runs/{STAGE}/executor-2", "role": "executor", "attempt": 2},
        ],
    )
    deleted, _, _ = _run_cleanup(ws)
    assert deleted and deleted[0]["id"] == "ps"


def test_truncated_operation_json_does_not_crash(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    journal = _journal(ws, "executor", 1)
    ops = journal / "operations"
    ops.mkdir(parents=True)
    (ops / "broken.json").write_text(
        '{"entities": [{"@type": "Process", "@id": "partial"',
        encoding="utf-8",
    )
    ids = journal_entity_ids(journal)
    assert ("Process", "partial") in ids


def test_legacy_category_prefix_rejected(tmp_path: Path) -> None:
    ok, reason = strict_project_category(f"{PROJECT}-old/extra")
    assert not ok and reason == "legacy_category_prefix"


def test_background_or_missing_category_skipped(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    _write_ops(_journal(ws, "executor", 1), [{"@type": "Flow", "@id": "bg"}])
    _attempts_doc(
        ws,
        [
            {"dir": f"runs/{STAGE}/executor-1", "role": "executor", "attempt": 1},
            {"dir": f"runs/{STAGE}/executor-2", "role": "executor", "attempt": 2},
        ],
    )

    def fetch(entity_type: str, entity_id: str):
        if entity_id == "bg":
            return {"name": "bg", "category": "Background/elem"}
        return {"name": entity_id, "category": f"{PROJECT}/ok"}

    deleted, skipped, _ = _run_cleanup(ws, fetch=fetch)
    assert not any(d["id"] == "bg" for d in deleted)
    assert any(s["id"] == "bg" for s in skipped)


def test_reviewer_directories_not_scanned(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    _write_ops(_journal(ws, "reviewer", 1), [{"@type": "Process", "@id": "rev"}])
    _write_ops(_journal(ws, "executor", 1), [{"@type": "Process", "@id": "w"}])
    _attempts_doc(
        ws,
        [
            {"dir": f"runs/{STAGE}/reviewer-1", "role": "reviewer", "attempt": 1},
            {"dir": f"runs/{STAGE}/executor-1", "role": "executor", "attempt": 1},
            {"dir": f"runs/{STAGE}/executor-2", "role": "executor", "attempt": 2},
        ],
    )
    _, _, removed = _run_cleanup(ws)
    assert ("Process", "rev", "rev") not in removed
    assert ("Process", "w", "w") in removed


def test_validate_target_category_rejects_old_prefix() -> None:
    validate_target_category(PROJECT)
    with pytest.raises(ValueError):
        validate_target_category(f"{PROJECT}-old/extra")


def test_attempt_dir_rejects_absolute_and_parent_segments(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    _write_ops(_journal(ws, "executor", 2), [{"@type": "Process", "@id": "safe"}])
    _attempts_doc(
        ws,
        [
            {"dir": "/etc/passwd", "role": "executor", "attempt": 1},
            {"dir": f"runs/{STAGE}/executor-2", "role": "executor", "attempt": 2},
        ],
    )
    deleted, _, removed = _run_cleanup(ws)
    assert not removed
    assert not deleted


def test_attempt_dir_must_stay_under_stage_runs(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    other = ws / "runs" / "03-dataset-mapping" / "executor-1" / "import-operations"
    _write_ops(other, [{"@type": "Process", "@id": "foreign"}])
    _attempts_doc(
        ws,
        [
            {
                "dir": "runs/03-dataset-mapping/executor-1",
                "role": "executor",
                "attempt": 1,
            },
            {"dir": f"runs/{STAGE}/executor-2", "role": "executor", "attempt": 2},
        ],
    )
    _, _, removed = _run_cleanup(ws)
    assert not removed


def test_salvage_pairs_type_and_id_within_object_fragment() -> None:
    text = (
        '{"@type": "Process", "@id": "p1"} '
        '{"@type": "Flow", "@id": "f1"} '
        '{"@type": "Process"} '
        '{"@id": "orphan"}'
    )
    salvaged = _salvage_entity_ids(text)
    assert salvaged == {("Process", "p1"), ("Flow", "f1")}


def test_salvage_does_not_zip_mismatched_global_order() -> None:
    text = '{"@id": "first-id"}{"@type": "Process", "@id": "real-p"}'
    salvaged = _salvage_entity_ids(text)
    assert ("Process", "real-p") in salvaged
    assert ("Process", "first-id") not in salvaged
