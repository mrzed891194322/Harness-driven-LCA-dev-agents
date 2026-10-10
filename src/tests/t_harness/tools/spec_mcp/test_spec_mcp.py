"""P5 acceptance: spec_mcp get_spec / submit / status / submit_handoff (scripted agent)."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
import yaml

from backend.core.agents import spec_mcp as host
from backend.core.workflow.spec.loader import load_stage_spec
from backend.core.workflow.spec.view import spec_view, spec_view_hash
from harness.tools.mcp.spec_mcp import main as server
from harness.tools.mcp.spec_mcp.spec_view import read_spec

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["items"],
    "additionalProperties": False,
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["item_id", "amount"],
                "properties": {"item_id": {"type": "string"}, "amount": {"type": "number"}},
            },
        }
    },
}
GOOD = {"items": [{"item_id": "a", "amount": 1.5}]}


def _project(root: Path) -> Path:
    stage = root / "harness" / "specs" / "s1"
    (stage / "deliverables").mkdir(parents=True)
    (stage / "examples").mkdir()
    (stage / "deliverables" / "bom.schema.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    (stage / "examples" / "bom.json").write_text(json.dumps(GOOD), encoding="utf-8")
    (stage / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "id": "s1",
                "deliverables": [
                    {"name": "bom", "path": "workspace/outputs/bom.json", "format": "json",
                     "schema": "deliverables/bom.schema.json", "example": "examples/bom.json",
                     "writer": "spec_mcp"},
                    {"name": "notes", "path": "workspace/outputs/notes.md", "format": "text",
                     "writer": "spec_mcp"},
                ],
                "acceptance": "acceptance.yaml",
                "permissions": "permissions.yaml",
            }
        ),
        encoding="utf-8",
    )
    (stage / "acceptance.yaml").write_text(
        yaml.safe_dump(
            {"version": 1, "deliverables": {"notes": [
                {"check": "nonempty_text", "params": {"min_chars": 10}, "summary": "notes 不少于 10 字"}
            ]}},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    (stage / "permissions.yaml").write_text(
        "version: 1\nroles: {executor: [worker-default], reviewer: [reviewer]}\n", encoding="utf-8"
    )
    (root / "harness" / "tools" / "mcp" / "spec_mcp").mkdir(parents=True)
    (root / "harness" / "tools" / "mcp" / "spec_mcp" / "mcp.yaml").write_text(
        (Path(server.__file__).parent / "mcp.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (root / "workspace").mkdir()
    return root


def _bind(monkeypatch, root: Path, role: str = "executor", **over) -> dict:
    entry = host.spec_mcp_server(
        project_root=root, workspace_root=root / "workspace", run_id="run-1", stage_id="s1",
        role=role, attempt=1, assignment_id=f"s1.{role}", spec_relative="harness/specs/s1/spec.yaml",
        handoff_relative="records/handoffs/s1.json",
    )
    env = dict(entry["env"])
    env.update(over)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = _project(tmp_path)
    _bind(monkeypatch, root)
    return root


def test_get_spec_matches_core_and_is_override_first(project):
    out = server.get_spec()
    assert out["ok"] and out["binding"]["stage"] == "s1"
    bom = out["spec"]["deliverables"][0]
    assert bom["schema"]["required"] == ["items"] and bom["example"] == GOOD
    core = load_stage_spec(project / "harness/specs/s1/spec.yaml", project_root=project,
                           relative="harness/specs/s1/spec.yaml")
    assert spec_view(core, project) == out["spec"]  # host first-context == tool output
    # user override (not in git) wins, read fresh on the next call, no restart
    override = project / "harness/.user/specs/s1/deliverables/bom.schema.json"
    override.parent.mkdir(parents=True)
    override.write_text(json.dumps({**SCHEMA, "title": "user"}), encoding="utf-8")
    again = server.get_spec()
    assert again["spec"]["deliverables"][0]["schema"]["title"] == "user"
    assert again["spec"]["sources"]["specs/s1/deliverables/bom.schema.json"] == "user"
    assert again["spec_hash"] != out["spec_hash"]


def test_submit_rejects_invalid_then_accepts_corrected(project):
    target = project / "workspace/outputs/bom.json"
    bad = server.submit("bom", {"items": [{"item_id": "a"}], "extra": 1})
    assert not bad["ok"] and bad["status"] == "failed"
    assert any("amount" in e for e in bad["errors"]) and any("extra" in e for e in bad["errors"])
    assert bad["hint"] and not target.exists()  # official path untouched
    # scripted agent self-corrects from the error list
    good = server.submit("bom", json.dumps(GOOD))
    assert good["ok"] and good["status"] == "passed"
    assert json.loads(target.read_text(encoding="utf-8")) == GOOD
    assert good["pending"] == ["notes"]


def test_acceptance_failure_rolls_back_and_handoff_gated(project):
    handoff = project / "workspace/records/handoffs/s1.json"
    refused = server.submit_handoff(status="ok", status_reason="done")
    assert not refused["ok"] and set(refused["pending"]) == {"bom", "notes"}
    assert not handoff.exists()
    short = server.submit("notes", "short")
    assert not short["ok"] and "nonempty_text" in short["errors"][0]
    assert not (project / "workspace/outputs/notes.md").exists()
    assert server.submit("bom", GOOD)["ok"]
    assert not server.submit_handoff(status="ok", status_reason="done")["ok"]
    assert server.submit("notes", "这份说明写得足够长了，覆盖全部条目。")["ok"]
    assert server.status()["ready_for_handoff"]
    done = server.submit_handoff(status="ok", status_reason="done", artifacts=["outputs/bom.json"])
    assert done["ok"], done
    body = json.loads(handoff.read_text(encoding="utf-8"))
    assert (body["stage"], body["role"], body["attempt"]) == ("s1", "executor", 1)
    # editing an accepted file afterwards makes it stale -> gate closes again
    (project / "workspace/outputs/bom.json").write_text("{}", encoding="utf-8")
    assert server.status()["pending"] == ["bom"]


def test_failed_handoff_always_allowed_for_rework(project):
    out = server.submit_handoff(status="failed", status_reason="upstream", rework_scope="model_changed",
                                rework_target_stage="s0")
    assert out["ok"], out


def test_stage_cannot_be_changed_by_agent(project, monkeypatch):
    for tool in (server.get_spec, server.submit, server.status, server.submit_handoff):
        params = set(inspect.signature(tool).parameters)
        assert not params & {"stage", "run_id", "role", "attempt"}, tool.__name__
    env = _bind(monkeypatch, project)
    payload = json.loads(env[host.BINDING_ENV])
    payload["stage"] = "s9"
    monkeypatch.setenv(host.BINDING_ENV, json.dumps(payload))  # tampered, old token
    out = server.get_spec()
    assert not out["ok"] and out["code"] == "binding_invalid"
    monkeypatch.setenv(host.TOKEN_ENV, "0" * 64)
    assert server.submit("bom", GOOD)["code"] == "binding_invalid"


def test_reviewer_cannot_submit(project, monkeypatch):
    _bind(monkeypatch, project, role="reviewer")
    assert not server.submit("bom", GOOD)["ok"]
    assert server.submit_handoff(status="passed", status_reason="ok")["ok"]


@pytest.mark.parametrize("breakage", ["missing_acceptance", "bad_schema", "bad_example", "no_manifest"])
def test_missing_or_invalid_spec_fails_closed(project, breakage):
    stage = project / "harness/specs/s1"
    if breakage == "missing_acceptance":
        (stage / "acceptance.yaml").unlink()
    elif breakage == "bad_schema":
        (stage / "deliverables/bom.schema.json").write_text('{"type": 7}', encoding="utf-8")
    elif breakage == "bad_example":
        (stage / "examples/bom.json").write_text('{"items": 1}', encoding="utf-8")
    else:
        (stage / "spec.yaml").unlink()
    if breakage != "bad_example":  # example validity is a core/GUI concern
        out = server.get_spec()
        assert not out["ok"] and out["code"] == "spec_invalid"
        assert server.submit_handoff(status="ok", status_reason="x")["code"] == "spec_invalid"
    with pytest.raises((ValueError, OSError)):
        load_stage_spec(stage / "spec.yaml", project_root=project, relative="harness/specs/s1/spec.yaml")


def test_view_hash_changes_with_spec_content(project):
    def h():
        core = load_stage_spec(project / "harness/specs/s1/spec.yaml", project_root=project,
                               relative="harness/specs/s1/spec.yaml")
        return spec_view_hash(spec_view(core, project))

    before = h()
    acc = project / "harness/specs/s1/acceptance.yaml"
    acc.write_text(acc.read_text(encoding="utf-8").replace("10 字", "20 字"), encoding="utf-8")
    assert h() != before
    assert read_spec(project, "specs/s1/spec.yaml").view()["deliverables"][1]["acceptance"] == ["notes 不少于 20 字"]


def test_unknown_check_fails_closed(project):
    acc = project / "harness/specs/s1/acceptance.yaml"
    acc.write_text(acc.read_text(encoding="utf-8").replace("nonempty_text", "nope"), encoding="utf-8")
    out = server.submit("notes", "x" * 40)
    assert not out["ok"] and "未知检查" in out["errors"][0]


# ---------------------------------------------------------------- host side

REPO = Path(__file__).resolve().parents[5]


def _launch(tmp_path, monkeypatch, stage_id: str, role: str = "executor"):
    from backend.core.runtime.capabilities import base_capabilities
    from backend.core.runtime.launch_spec import build_session_launch_spec
    from backend.core.workflow.config.loader import load_workflow

    key = tmp_path / "spec_mcp.key"
    key.write_bytes(b"k" * 64)
    monkeypatch.setattr(host, "ensure_key", lambda _root: key)  # never touch repo .local/
    workflow = load_workflow(REPO / "harness/LCA-main.yaml", project_root=REPO,
                             capabilities=base_capabilities())
    stage = workflow.stage_by_id(stage_id)
    assignment = workflow.assignments[f"{stage_id}.{role}"]
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    return build_session_launch_spec(
        workflow, workflow.bundles[assignment.assignment_id], project_root=REPO,
        workspace_root=workspace, worker="pi", model="frozen-model", stage=stage,
        assignment=assignment, run_id="r", attempt=1, session_key="k", run_context={"run_id": "r"},
    )


def test_launch_binds_spec_mcp_first_context_and_guard(tmp_path, monkeypatch):
    spec = _launch(tmp_path, monkeypatch, "03-dataset-mapping")
    assert spec.system_sections[0].id == "spec_context"
    first = spec.system_sections[0].content
    assert "process-mapping" in first and '"$schema"' in first  # schema lives in first context
    prompt = spec.system_sections[1].content
    assert "harness/specs/" not in prompt and '"$schema"' not in prompt
    assert prompt.rstrip().endswith("以 spec_mcp 为准，用 submit 交付")
    assert "spec_mcp" in spec.mcp_bindings
    env = spec.mcp_bindings["spec_mcp"]["env"]
    binding = json.loads(env[host.BINDING_ENV])
    assert (binding["stage"], binding["role"], binding["attempt"]) == ("03-dataset-mapping", "executor", 1)
    policy = spec.permission_policy
    assert "mcp__spec_mcp__*" in policy.allowed_tools
    assert any(g.endswith("workspace/outputs/inventory/process-mapping.json") for g in policy.denied_write_globs)


def test_bundle_hash_tracks_user_spec_override(tmp_path, monkeypatch):
    before = _launch(tmp_path, monkeypatch, "02-inventory-extraction").bundle_hash
    override = REPO / "harness/.user/specs/02-inventory-extraction/acceptance.yaml"
    assert not override.exists(), "test needs a clean harness/.user/"
    override.parent.mkdir(parents=True)
    try:
        text = (REPO / "harness/specs/02-inventory-extraction/acceptance.yaml").read_text(encoding="utf-8")
        override.write_text(text + "\n# user tweak\n", encoding="utf-8")
        same_view = _launch(tmp_path, monkeypatch, "02-inventory-extraction").bundle_hash
        override.write_text(text.replace("summary:", "summary: 用户版", 1), encoding="utf-8")
        changed = _launch(tmp_path, monkeypatch, "02-inventory-extraction").bundle_hash
    finally:
        import shutil

        shutil.rmtree(REPO / "harness/.user/specs/02-inventory-extraction")
        for p in (REPO / "harness/.user/specs", REPO / "harness/.user"):
            if p.is_dir() and not any(p.iterdir()):
                p.rmdir()
    assert changed != before
    assert same_view != changed


def test_real_stdio_child_exposes_exactly_four_tools(project):
    import os
    import subprocess
    import sys

    probe = REPO / "src/tests/t_core/orchestrator/stdio_mcp_probe.py"
    env = {k: os.environ[k] for k in (host.BINDING_ENV, host.TOKEN_ENV, host.KEY_FILE_ENV)}
    server_entry = {"command": sys.executable, "args": [str(Path(server.__file__))], "env": env}
    out = subprocess.run(
        [sys.executable, str(probe)],
        input=json.dumps({"server": server_entry, "name": "get_spec", "arguments": {"stage": "s9"}}),
        capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0, out.stderr
    payload = json.loads(out.stdout)
    tools = {t["name"]: t for t in payload["tools"]}
    assert sorted(tools) == ["get_spec", "status", "submit", "submit_handoff"]
    for tool in tools.values():
        props = (tool.get("inputSchema") or tool.get("input_schema") or {}).get("properties") or {}
        assert not set(props) & {"stage", "run_id", "role", "attempt"}, tool["name"]
    print(json.dumps(payload["result"], ensure_ascii=False)[:400])
    assert payload["result"]["binding"]["stage"] == "s1"  # stage arg never rebinds


def test_unit_group_acceptance(monkeypatch, tmp_path):
    from harness.tools.shared.control_openlca import workflow as olca
    from harness.tools.shared.lca_artifacts import checks

    def inventory(unit):
        ex = {"isInput": True, "amount": 2.0, "flow": {"@id": "f", "name": "electricity"},
              "defaultProvider": {"@id": "p"}}
        if unit:
            ex["unit"] = {"name": unit}
        return [{"entity_type": "Process", "id": "fg", "path": "processes/fg.json",
                 "data": {"exchanges": [ex]}}]

    units = {("p", "f"): {"name": "kWh"}}
    monkeypatch.setattr(checks, "current_provider_units", lambda ctx: units)
    for unit, ok in (("MJ", True), ("kWh", True), ("kg", False), (None, False)):
        monkeypatch.setattr(olca, "load_lci_inventory", lambda _d, u=unit: (inventory(u), []))
        errors, _ = checks.exchange_unit_errors(None, tmp_path)
        assert (errors == []) is ok, (unit, errors)
    # transport: kg*km against t*km is the same group (converted with a note), kg is not
    units[("p", "f")] = {"name": "t*km"}
    monkeypatch.setattr(olca, "load_lci_inventory", lambda _d: (inventory("kg*km"), []))
    errors, notes = checks.exchange_unit_errors(None, tmp_path)
    assert errors == [] and notes
    monkeypatch.setattr(olca, "load_lci_inventory", lambda _d: (inventory("kg"), []))
    assert checks.exchange_unit_errors(None, tmp_path)[0]
    # no current-model provider record -> actionable fix hint
    units.clear()
    errors, _ = checks.exchange_unit_errors(None, tmp_path)
    assert errors and "validate_providers_batch" in errors[0]
