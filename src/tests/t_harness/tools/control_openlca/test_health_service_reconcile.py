"""health_service cleanup must not create workspace/records/."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from harness.tools.shared.control_openlca import health_service


def test_reconcile_scans_run_import_operations_without_records_dir(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    journal = ws / "runs" / "04-openlca-reporting" / "executor-1" / "import-operations"
    journal.mkdir(parents=True)
    (journal / "current.json").write_text(
        '{"operation_id": "op-1", "endpoint": "http://127.0.0.1:8080", "target_category": "proj"}',
        encoding="utf-8",
    )
    ops = journal / "operations"
    ops.mkdir()
    (ops / "op-1.json").write_text(
        '{"identity": {"endpoint": "http://127.0.0.1:8080", "category": "proj"}}',
        encoding="utf-8",
    )

    with (
        patch(
            "harness.tools.shared.control_openlca.health_service.run_cleanup_output",
            return_value={"ok": True},
        ),
        patch(
            "harness.tools.shared.control_openlca.health_service.reconcile_cleanup"
        ) as reconcile,
        patch(
            "harness.tools.shared.control_openlca.health_service.serialized_ipc",
            side_effect=lambda fn, **kwargs: fn,
        ),
    ):
        health_service.cleanup("127.0.0.1", 8080, "proj", confirm=True, workspace=ws)

    assert reconcile.call_count == 1
    assert reconcile.call_args[0][0] == journal
    assert not (ws / "records").exists()
