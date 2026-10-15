from __future__ import annotations

import json
from pathlib import Path

from harness.tools.shared.control_openlca.attempt_cleanup import (
    cleanup_prior_attempt_imports,
    validate_target_category,
)


def test_cleanup_skips_overlap_and_orders_deletes(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    stage = "04-openlca-reporting"
    old = ws / "runs" / stage / "executor-1" / "import-operations" / "operations"
    old.mkdir(parents=True)
    (old / "a.json").write_text(
        json.dumps(
            {
                "entities": [
                    {"@type": "Flow", "@id": "shared"},
                    {"@type": "Process", "@id": "p1"},
                    {"@type": "ProductSystem", "@id": "ps1"},
                ]
            }
        ),
        encoding="utf-8",
    )
    current = ws / "runs" / stage / "executor-2" / "import-operations" / "operations"
    current.mkdir(parents=True)
    (current / "b.json").write_text(
        json.dumps({"entities": [{"@type": "Flow", "@id": "shared"}]}),
        encoding="utf-8",
    )
    removed: list[tuple[str, str]] = []

    def delete(entity_type: str, entity_id: str) -> None:
        removed.append((entity_type, entity_id))

    report = cleanup_prior_attempt_imports(
        ws,
        stage_id=stage,
        current_attempt=2,
        accepted_attempt=None,
        delete_entity=delete,
        protected_ids={("Flow", "shared")},
    )
    assert ("Flow", "shared") not in removed
    assert [row["type"] for row in report] == ["ProductSystem", "Process"]


def test_validate_target_category_rejects_old_prefix() -> None:
    validate_target_category("202606-harness-agent-LCA")
    try:
        validate_target_category("202606-harness-agent-LCA-old/extra")
    except ValueError as exc:
        assert "refusing" in str(exc)
    else:
        raise AssertionError("expected refusal")
