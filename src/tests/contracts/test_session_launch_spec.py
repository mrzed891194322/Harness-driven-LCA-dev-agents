from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from core.contracts.session_launch_spec import (
    ModelProfile,
    PermissionPolicy,
    SessionLaunchSpec,
    SystemSection,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads(
    (
        PROJECT_ROOT
        / "src/backend/contracts/session_launch_spec.schema.json"
    ).read_text(encoding="utf-8")
)


def test_launch_spec_validates_against_schema() -> None:
    spec = SessionLaunchSpec(
        run_id="r1",
        stage_id="s1",
        assignment_id="a1",
        role="executor",
        attempt=1,
        session_key="k1",
        execution_id="e1",
        bundle_hash="abc12345",
        input_snapshot_hash="def67890",
        model_profile=ModelProfile(
            profile_id="default",
            provider="anthropic",
            model_id="claude-sonnet-4-5",
        ),
        system_sections=[
            SystemSection(id="p", content="hello", source_hash="h"),
        ],
        turn_context={"handoff_path": "workspace/x.json"},
        knowledge_bindings=[],
        resource_bindings={"project_root": str(PROJECT_ROOT)},
        mcp_bindings={},
        permission_policy=PermissionPolicy(
            allowed_tools=["read"],
            allowed_read_globs=["/**"],
            allowed_write_globs=["/workspace/**"],
        ),
        session_storage={"agent_dir": "/tmp/a", "session_file": "/tmp/a/s.jsonl"},
    )
    jsonschema.validate(spec.to_dict(), SCHEMA)
