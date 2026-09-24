"""Exercise external MCP registration, actual stdio calls, and dependency boundaries."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

from core.agents.mcp import mcp_servers_for_tools
from core.agents.providers.claude.session import write_claude_mcp
from core.agents.providers.codex.session import mcp_overrides
from core.agents.providers.opencode.session import write_opencode_mcp
from core.agents.providers.pi.session import write_pi_mcp
from core.runtime.capabilities import base_capabilities
from core.workflow.config.loader import load_workflow
from core.workflow.execution.handoff import read_handoff
from core.workflow.execution.session_bind import build_session_config
from harness.tools.lca_artifacts.handoff import validate as validate_handoff
from tests.conftest import PROJECT_ROOT


def _workflow(tmp_path, server):
    specs = tmp_path / "harness" / "specs" / "work"
    specs.mkdir(parents=True)
    (specs / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "id": "work",
                "inputs": [],
                "outputs": [],
                "acceptance": {"checks": []},
                "lifecycle": {"on_reviewer_passed": []},
                "handoff": {"checks": []},
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    path = tmp_path / "workflow.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "id": "external",
                "registry": {"tools": {"external.echo": server}},
                "stages": [
                    {
                        "id": "work",
                        "spec": "harness/specs/work/spec.yaml",
                        "steps": ["writer", "reviewer"],
                    }
                ],
                "assignments": {
                    "writer": {
                        "role": "executor",
                        "tools": ["external.echo"],
                    },
                    "reviewer": {"role": "reviewer", "tools": []},
                },
            }
        )
    )
    return load_workflow(path, project_root=tmp_path, capabilities=base_capabilities())


def _call(server, name, arguments):
    # Exercise the actual protocol without sharing pytest's imports or runtime,
    # just like a worker's MCP connection.
    probe = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("stdio_mcp_probe.py"))],
        input=json.dumps({"server": server, "name": name, "arguments": arguments}),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert probe.returncode == 0, probe.stderr
    payload = json.loads(probe.stdout)
    return payload["result"], payload["tools"]


def test_external_mcp_registration_and_real_stdio_call(tmp_path):
    script = tmp_path / "external.py"
    script.write_text("""from mcp.server import MCPServer
import os
import sys
mcp = MCPServer("independent-echo")
@mcp.tool(structured_output=True)
def echo(value: str) -> dict[str, object]:
    return {"value": os.environ["PREFIX"] + value,
            "project_imports": [name for name in sys.modules if name.startswith(("harness.", "scripts."))]}
mcp.run()
""")
    server = {
        "command": sys.executable,
        "args": [str(script)],
        "env": {"PREFIX": "hello ", "prompt": "opaque tool setting"},
    }
    workflow = _workflow(tmp_path, server)
    config = build_session_config(
        workflow,
        workflow.bundles["writer"],
        project_root=tmp_path,
        workspace_root=tmp_path / "workspace",
        worker="codex",
        model="test",
        stage=workflow.stages[0],
        assignment=workflow.assignments["writer"],
        run_id="external-run",
        attempt=1,
    )
    bound = config.mcp_servers["external.echo"]
    assert bound["args"] == server["args"]
    assert bound["env"] == server["env"]
    assert bound["tool_timeout_sec"] == 60
    assert not (tmp_path / "workspace" / "tmp" / "mcp-context").exists()
    result, _ = _call(bound, "echo", {"value": "world"})
    assert result == {"value": "hello world", "project_imports": []}


def test_all_worker_renderers_preserve_external_launch_config(tmp_path):
    original = {
        "command": "/a path/bin/uv",
        "args": ["run", "python", "external.py", "a b"],
        "env": {"TOKEN": "literal $value", "MODE": "external"},
        "tool_timeout_sec": 123,
    }
    servers = mcp_servers_for_tools(["external.echo"], {"external.echo": original})
    rendered = tomllib.loads("\n".join(mcp_overrides(servers)))["mcp_servers"][
        "external.echo"
    ]
    for key in ("command", "args", "env", "tool_timeout_sec"):
        assert rendered[key] == original[key]
    for writer in (write_claude_mcp, write_pi_mcp):
        path = tmp_path / "mcp.json"
        writer(path, servers)
        entry = json.loads(path.read_text())["mcpServers"]["external.echo"]
        for key in ("command", "args", "env"):
            assert entry[key] == original[key]
        assert entry["timeout"] == 123000
    entry = write_opencode_mcp(servers)["external.echo"]
    assert entry["command"] == [original["command"], *original["args"]]
    assert entry["environment"] == original["env"]
    assert entry["timeout"] == 123000


@pytest.mark.parametrize(
    "patch",
    [
        {"transport": "http", "url": "https://example.invalid/mcp"},
        {"transport": "sse"},
        {"transport": "unknown"},
        {"command": ""},
        {"args": "not-a-list"},
        {"runtime": "invalid"},
        {"tool_timeout_sec": 0},
        {"tool_timeout_sec": True},
    ],
)
def test_invalid_launch_config_rejected_during_load(tmp_path, patch):
    with pytest.raises(ValueError):
        _workflow(tmp_path, {"command": "external", **patch})


def test_generic_handoff_leaves_domain_extension_to_adapter(tmp_path):
    path = tmp_path / "handoff.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "role": "executor",
                "stage": "s",
                "attempt": 1,
                "status": "ok",
                "status_reason": "done",
                "rework_scope": "another-domain",
            }
        )
    )
    payload = read_handoff(path, role="executor", stage="s", attempt=1)
    with pytest.raises(ValueError, match="rework_scope"):
        validate_handoff(payload, label="writer")


@pytest.mark.parametrize("module", ["control_openlca", "lca_artifacts"])
def test_standalone_tools_do_not_import_workflow(module):
    code = f"""
import importlib.abc
import sys
class BlockWorkflow(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        blocked = (
            "core.workflow",
            "domains.lca",
            "services",
            "gui",
            "scripts",
        )
        if fullname in blocked or any(fullname.startswith(b + ".") for b in blocked):
            raise AssertionError(
                "standalone tool attempted forbidden import: " + fullname
            )
sys.meta_path.insert(0, BlockWorkflow())
import harness.tools.{module}.main
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


def test_standalone_artifact_mcp_needs_no_workflow_context(tmp_path):
    import hashlib

    path = tmp_path / "document.txt"
    path.write_text("independent artifact")
    result, _ = _call(
        {
            "command": sys.executable,
            "args": [str(PROJECT_ROOT / "harness/tools/lca_artifacts/main.py")],
        },
        "read_artifact",
        {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        },
    )
    assert result["items"] == [{"text": "independent artifact"}]


def test_standalone_openlca_mcp_uses_explicit_journal(tmp_path):
    result, tools = _call(
        {
            "command": sys.executable,
            "args": [str(PROJECT_ROOT / "harness/tools/control_openlca/main.py")],
        },
        "get_import_operation",
        {
            "operation_dir": str(tmp_path),
            "scope_id": "independent",
            "request_id": "missing",
        },
    )
    assert result["status"] == "not_found"
    import_tool = next(tool for tool in tools if tool["name"] == "import_lci")
    assert {"lci_dir", "target_category", "operation_dir", "scope_id"} <= set(
        import_tool["inputSchema"]["required"]
    )


def test_report_render_does_not_follow_existing_temp_symlink(tmp_path):
    from harness.tools.lca_artifacts import offline_report as report

    target = tmp_path / "report.md"
    target.write_text(
        "\n".join(
            "\n".join(report.markers(name)) for name in ("inventory", "mapping", "lcia")
        )
    )
    other = tmp_path / "other.txt"
    other.write_text("untouched")
    target.with_suffix(".tmp").symlink_to(other)
    result = report.render(target, [], [], [])
    assert result["ok"]
    assert other.read_text() == "untouched"
    assert report.report_table_errors(target, [], [], []) == []


def test_check_snapshot_does_not_hide_changes_or_leak_between_calls(tmp_path):
    from harness.tools.lca_artifacts.snapshot_io import (
        check_snapshot,
        load_json,
        sha256_file,
    )

    path = tmp_path / "input.json"
    path.write_text('{"value": 1}')

    @check_snapshot
    def inspect():
        first = sha256_file(path)
        assert load_json(path) == {"value": 1}
        path.write_text('{"value": 2}')
        assert sha256_file(path) != first
        assert load_json(path) == {"value": 2}

    inspect()
    path.write_text('{"value": 3}')
    assert load_json(path) == {"value": 3}


@pytest.mark.parametrize("tool", ["artifacts", "openlca"])
def test_workflow_adapter_entrypoints_preserve_context_and_response(tmp_path, tool):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "stage": "inventory-step",
                "attempt": 1,
                "role": "reviewer",
                "assignment": "reviewer",
                "workspace": str(workspace),
                "metadata": {"lca": {"phase": "inventory"}},
            }
        )
    )
    if tool == "artifacts":
        script, method, arguments = (
            PROJECT_ROOT / "harness/tools/lca_artifacts/workflow_mcp.py",
            "get_validation_state",
            {"profile": "inventory"},
        )
    else:
        script, method, arguments = (
            PROJECT_ROOT / "harness/tools/control_openlca/workflow_mcp.py",
            "get_import_operation",
            {"request_id": "missing"},
        )
    result, listed = _call(
        {
            "command": sys.executable,
            "args": [str(script), "--context-file", str(context)],
        },
        method,
        arguments,
    )
    assert result["schema_version"] == 2
    assert result["artifacts"]
    assert (workspace / "memory/evidence/run-1/manifest.json").is_file()
    if tool == "artifacts":
        assert result["checks"][0]["status"] == "not_run"
    else:
        imported = next(item for item in listed if item["name"] == "import_lci")
        assert set(imported["inputSchema"]["required"]) == {
            "request_id",
            "preflight_id",
        }
