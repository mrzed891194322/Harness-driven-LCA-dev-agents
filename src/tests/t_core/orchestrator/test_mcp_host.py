"""Host MCP fail-closed behaviour and timeout honouring."""

from __future__ import annotations

import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core.runtime.context import RunContext
from core.runtime.mcp_host import invoke_tool, normalize_check_result
from core.workflow.config.models import ToolSpec


def _tool(*, script: Path, timeout_sec: int = 30) -> ToolSpec:
    return ToolSpec(
        tool_id="probe",
        transport="stdio",
        command=sys.executable,
        args=[str(script)],
        tool_timeout_sec=timeout_sec,
    )


class McpHostFailClosedTests(unittest.TestCase):
    def test_plain_text_result_is_acceptance_failure(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script = root / "plain.py"
            script.write_text(
                textwrap.dedent(
                    """\
                    import json, sys
                    def reply(mid, result):
                        sys.stdout.write(json.dumps({"jsonrpc":"2.0","id":mid,"result":result})+"\\n")
                        sys.stdout.flush()
                    for raw in sys.stdin:
                        msg = json.loads(raw)
                        method = msg.get("method")
                        mid = msg.get("id")
                        if method == "initialize":
                            reply(mid, {"protocolVersion":"2025-11-25","capabilities":{},"serverInfo":{"name":"p","version":"1"}})
                        elif method == "notifications/initialized":
                            continue
                        elif method == "tools/call":
                            reply(mid, {"content":[{"type":"text","text":"done"}]})
                        elif mid is not None:
                            reply(mid, {})
                    """
                ),
                encoding="utf-8",
            )
            run_ctx = RunContext(
                project_root=root,
                workspace_root=root / "workspace",
                run_id="r",
                stage_id="s",
                assignment_id="a",
                attempt=1,
                role="executor",
            )
            (root / "workspace").mkdir()
            result = invoke_tool(
                _tool(script=script),
                "validate",
                {},
                run_ctx=run_ctx,
                project_root=root,
            )
            self.assertFalse(result.ok)
            self.assertEqual(result.status, "failed")

    def test_timeout_uses_declared_tool_timeout_sec(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            script = root / "slow.py"
            script.write_text("print('noop')\n", encoding="utf-8")
            run_ctx = RunContext(
                project_root=root,
                workspace_root=root / "workspace",
                run_id="r",
                stage_id="s",
                assignment_id="a",
                attempt=1,
                role="executor",
            )
            (root / "workspace").mkdir()
            captured: dict[str, float] = {}

            def fake_stdio(*_args, **kwargs):
                captured["timeout_sec"] = float(kwargs["timeout_sec"])
                return {"ok": True, "status": "passed", "summary": "ok"}

            with patch("core.runtime.mcp_host._stdio_call", side_effect=fake_stdio):
                result = invoke_tool(
                    _tool(script=script, timeout_sec=240),
                    "validate",
                    {},
                    run_ctx=run_ctx,
                    project_root=root,
                )
            self.assertTrue(result.ok)
            self.assertEqual(captured["timeout_sec"], 240.0)

    def test_normalize_requires_ok_or_status(self) -> None:
        result = normalize_check_result({"summary": "x"})
        self.assertFalse(result.ok)
        self.assertIn("ok/status", result.summary)


if __name__ == "__main__":
    unittest.main()
