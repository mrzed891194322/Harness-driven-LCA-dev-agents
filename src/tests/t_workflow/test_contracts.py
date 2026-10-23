"""#2: SessionLaunchSpec has one Python source; exported schema/TS stay in sync; built specs validate."""
from __future__ import annotations

import json
import subprocess
import sys

import jsonschema

from tests.t_workflow.conftest import REPO
from tests.t_workflow.test_pi_driver import MODEL, FakeRuntime, _req, _setup
from backend.workflow.pi_driver import PiDriver

SCRIPT = REPO / "src/scripts/export_contracts.py"
SCHEMA = REPO / "src/backend/core/contracts/session_launch_spec.schema.json"


def test_exported_contracts_match_committed_files():
    p = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stdout + p.stderr


def test_launch_specs_validate_against_schema(wf_root):
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    node = _setup(wf_root)
    d = PiDriver(wf_root, MODEL, runtime=FakeRuntime())
    for agent in ("executor", "reviewer"):
        spec, _ = d.launch_spec(_req(wf_root, node, agent=agent))
        payload = spec.to_dict()
        jsonschema.validate(payload, schema)
        assert payload["schema_version"] == 2 and payload["node"] == "n1" and payload["rev"] == 0
        assert not {"stage_id", "assignment_id", "execution_id", "bundle_hash", "input_snapshot_hash"} & set(payload)
    bad = dict(payload, stage_id="x")
    try:
        jsonschema.validate(bad, schema)
    except jsonschema.ValidationError:
        pass
    else:
        raise AssertionError("unknown field accepted")
