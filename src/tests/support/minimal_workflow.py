"""Helpers to write minimal new-format workflows (spec.yaml + rules, no providers)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import yaml


def write_tree(root: Path) -> None:
    """Create rule/knowledge/tool stubs under a fake project root."""
    (root / "harness" / "knowledge").mkdir(parents=True, exist_ok=True)
    (root / "harness" / "knowledge" / "README.md").write_text("# k\n", encoding="utf-8")
    rules = root / "harness" / "rules" / "project"
    rules.mkdir(parents=True, exist_ok=True)
    for name in ("write-boundary.md", "runtime.md", "paths.md", "extra.md"):
        (rules / name).write_text(f"# {name}\n", encoding="utf-8")
    tools = root / "harness" / "tools" / "probe"
    tools.mkdir(parents=True, exist_ok=True)
    (tools / "main.py").write_text("print('ok')\n", encoding="utf-8")


def write_stage_spec(
    root: Path,
    *,
    stage_id: str = "s1",
    outputs: list[dict] | None = None,
    acceptance: list[dict] | None = None,
    on_reviewer_passed: list[dict] | None = None,
    handoff_checks: list[dict] | None = None,
    tool: str = "probe",
) -> str:
    """Write ``harness/specs/<stage_id>/spec.yaml`` and return relative path."""
    specs = root / "harness" / "specs" / stage_id
    specs.mkdir(parents=True, exist_ok=True)
    if acceptance is None:
        acceptance = [
            {
                "id": "ping",
                "tool": tool,
                "call": "validate",
                "state_call": "get_state",
                "arguments": {},
            }
        ]
    if on_reviewer_passed is None:
        on_reviewer_passed = []
    if handoff_checks is None:
        handoff_checks = []
    if outputs is None:
        outputs = [
            {
                "path": "workspace/out.txt",
                "kind": "file",
                "required": True,
            }
        ]
    payload = {
        "version": 1,
        "id": stage_id,
        "inputs": [],
        "outputs": outputs,
        "acceptance": {"checks": acceptance},
        "lifecycle": {"on_reviewer_passed": on_reviewer_passed},
        "handoff": {"checks": handoff_checks},
    }
    relative = f"harness/specs/{stage_id}/spec.yaml"
    (root / relative).write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return relative


def write_fake_mcp_server(
    root: Path, *, relative: str = "harness/tools/probe/main.py"
) -> Path:
    """Write a tiny newline JSON-RPC MCP stub (no mcp package framing)."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        textwrap.dedent(
            """\
            import json
            import sys

            def reply(message_id, result):
                sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": message_id, "result": result}) + "\\n")
                sys.stdout.flush()

            for raw in sys.stdin:
                line = raw.strip()
                if not line:
                    continue
                message = json.loads(line)
                method = message.get("method")
                message_id = message.get("id")
                if method == "initialize":
                    reply(
                        message_id,
                        {
                            "protocolVersion": "2025-11-25",
                            "capabilities": {},
                            "serverInfo": {"name": "probe", "version": "1"},
                        },
                    )
                elif method == "notifications/initialized":
                    continue
                elif method == "tools/list":
                    reply(
                        message_id,
                        {
                            "tools": [
                                {"name": "validate", "inputSchema": {"type": "object"}},
                                {"name": "get_state", "inputSchema": {"type": "object"}},
                                {"name": "noop", "inputSchema": {"type": "object"}},
                            ]
                        },
                    )
                elif method == "tools/call":
                    name = message["params"]["name"]
                    payload = {
                        "ok": True,
                        "status": "passed",
                        "summary": name,
                        "errors": [],
                        "warnings": [],
                    }
                    reply(
                        message_id,
                        {
                            "content": [{"type": "text", "text": json.dumps(payload)}],
                            "structuredContent": payload,
                        },
                    )
                elif message_id is not None:
                    reply(message_id, {})
            """
        ),
        encoding="utf-8",
    )
    return path


def write_minimal_workflow(
    root: Path,
    *,
    workflow_id: str = "patch-test",
    filename: str = "patch-test.yaml",
    stage_id: str = "s1",
    tool_id: str = "probe",
    tool_command: str = "python",
    tool_args: list[str] | None = None,
    tool_runtime: dict | None = None,
    acceptance: list[dict] | None = None,
    on_reviewer_passed: list[dict] | None = None,
    executor_tools: list[str] | None = None,
    executor_rules: dict | None = None,
    knowledge_provider: str = "local_files",
) -> Path:
    """Write a complete independent workflow YAML + stage spec under ``root``."""
    write_tree(root)
    spec_rel = write_stage_spec(
        root,
        stage_id=stage_id,
        acceptance=acceptance,
        on_reviewer_passed=on_reviewer_passed,
        tool=tool_id,
    )
    if tool_args is None:
        tool_args = [f"harness/tools/{tool_id}/main.py"]
    tool_entry: dict = {
        "transport": "stdio",
        "command": tool_command,
        "args": tool_args,
    }
    if tool_runtime:
        tool_entry["runtime"] = tool_runtime
    payload = {
        "id": workflow_id,
        "registry": {
            "rules": {
                "workspace_boundary": "harness/rules/project/write-boundary.md",
                "runtime": "harness/rules/project/runtime.md",
                "paths": "harness/rules/project/paths.md",
                "extra_rule": "harness/rules/project/extra.md",
            },
            "tools": {tool_id: tool_entry},
            "knowledge": {
                "workspace_knowledge": {
                    "kind": "local_dir",
                    "path": "harness/knowledge/",
                    "provider": knowledge_provider,
                }
            },
        },
        "defaults": {
            "rules": ["workspace_boundary", "runtime", "paths"],
            "knowledge": ["workspace_knowledge"],
        },
        "stages": [
            {
                "id": stage_id,
                "spec": spec_rel,
                "steps": [
                    {"assignment": f"{stage_id}.executor"},
                    {"assignment": f"{stage_id}.reviewer"},
                ],
            }
        ],
        "assignments": {
            f"{stage_id}.executor": {
                "role": "executor",
                "tools": executor_tools if executor_tools is not None else [tool_id],
                "rules": executor_rules
                if executor_rules is not None
                else {"add": ["extra_rule"], "remove": ["paths"]},
            },
            f"{stage_id}.reviewer": {
                "role": "reviewer",
                "tools": [],
            },
        },
    }
    path = root / "harness" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return path
