from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.services.openlca_attempt_cleanup import maybe_cleanup_before_openlca_write
from backend.core.workflow.workspace.index import (
    register_attempt,
    should_run_openlca_attempt_cleanup,
)

STAGE = "04-openlca-reporting"


def test_should_not_run_openlca_cleanup_on_first_attempt(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    register_attempt(ws, STAGE, "executor", 1, "run-a", origin="whole-lca")
    assert not should_run_openlca_attempt_cleanup(
        ws, STAGE, role="executor", attempt=1
    )


def test_second_attempt_writes_openlca_deleted_to_attempts_json(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    project = tmp_path
    journal1 = ws / "runs" / STAGE / "executor-1" / "import-operations" / "operations"
    journal1.mkdir(parents=True)
    (journal1 / "a.json").write_text(
        json.dumps({"entities": [{"@type": "Process", "@id": "p-old"}]}),
        encoding="utf-8",
    )
    register_attempt(ws, STAGE, "executor", 1, "run-a")
    register_attempt(ws, STAGE, "executor", 2, "run-b")

    class FakeEntity:
        id = "p-old"
        name = "p-old"
        category = "202606-harness-agent-LCA/x"

        def to_ref(self):
            return self

    class FakeClient:
        def get(self, _model, _entity_id):
            raise AssertionError("full data/get must not be used in cleanup")

        def get_descriptor(self, _model, entity_id):
            del entity_id
            return FakeEntity()

        def delete(self, _ref):
            return None

    with patch(
        "backend.services.openlca_attempt_cleanup.connect_ipc",
        return_value=FakeClient(),
    ), patch(
        "backend.services.openlca_attempt_cleanup.close_ipc_client",
        lambda _c: None,
    ), patch(
        "backend.services.openlca_attempt_cleanup.openlca_endpoint",
        return_value=("127.0.0.1", 1),
    ):
        maybe_cleanup_before_openlca_write(
            project,
            ws,
            stage_id=STAGE,
            role="executor",
            attempt=2,
        )

    doc = json.loads((ws / "runs" / STAGE / "attempts.json").read_text(encoding="utf-8"))
    row = next(r for r in doc["attempts"] if r["attempt"] == 2)
    assert row.get("openlca_deleted")
    assert not should_run_openlca_attempt_cleanup(
        ws, STAGE, role="executor", attempt=2
    )


def test_unreachable_openlca_records_skip_and_raises(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    journal1 = ws / "runs" / STAGE / "executor-1" / "import-operations" / "operations"
    journal1.mkdir(parents=True)
    (journal1 / "a.json").write_text(
        json.dumps({"entities": [{"@type": "Process", "@id": "p-old"}]}),
        encoding="utf-8",
    )
    register_attempt(ws, STAGE, "executor", 1, "run-a")
    register_attempt(ws, STAGE, "executor", 2, "run-b")

    def _boom(*_a, **_k):
        raise ConnectionError("ipc down")

    with patch(
        "backend.services.openlca_attempt_cleanup.connect_ipc",
        side_effect=_boom,
    ), patch(
        "backend.services.openlca_attempt_cleanup.openlca_endpoint",
        return_value=("127.0.0.1", 1),
    ), patch(
        "backend.services.openlca_attempt_cleanup.cleanup_prior_attempt_imports",
    ) as cleanup_mock, pytest.raises(RuntimeError, match="openlca unreachable"):
        maybe_cleanup_before_openlca_write(
            tmp_path,
            ws,
            stage_id=STAGE,
            role="executor",
            attempt=2,
        )

    cleanup_mock.assert_not_called()
    doc = json.loads((ws / "runs" / STAGE / "attempts.json").read_text(encoding="utf-8"))
    row = next(r for r in doc["attempts"] if r["attempt"] == 2)
    assert row.get("openlca_skipped") == [{"reason": "openlca_unreachable"}]
    assert row.get("openlca_deleted") is None
