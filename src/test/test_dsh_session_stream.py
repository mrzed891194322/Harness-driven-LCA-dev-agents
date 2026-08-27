"""Tests for DSH session log formatting used by the GUI terminal."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401,E402

from functions.utils.executor.private_utils.dsh_session_stream import (  # noqa: E402
    DshSessionLogTailer,
    format_dsh_event,
    project_key,
)


class DshSessionStreamTests(unittest.TestCase):
    def test_project_key_matches_dsh_layout(self) -> None:
        key = project_key("/home/yuandu/Programming/202606-harness-agent-LCA")
        self.assertEqual(
            key,
            "--home-yuandu-Programming-202606-harness-agent-LCA--",
        )

    def test_format_tool_call(self) -> None:
        text = format_dsh_event(
            {
                "type": "tool/call",
                "data": {
                    "name": "skill",
                    "arguments": '{"name":"whole-lca"}',
                },
            }
        )
        self.assertIn("[DSH tool] skill", text)
        self.assertIn("whole-lca", text)

    def test_format_assistant_message_skips_system_reminder(self) -> None:
        text = format_dsh_event(
            {
                "type": "assistant/message",
                "data": {
                    "message": {
                        "content": [
                            {
                                "type": "text",
                                "text": "<system-reminder>hidden</system-reminder>visible line",
                            }
                        ],
                    },
                },
            }
        )
        self.assertIn("visible line", text)
        self.assertNotIn("hidden", text)

    def test_tailer_reads_plain_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sessions_root = Path(temp_dir)
            project_root = Path("/tmp/example-project")
            key = project_key(str(project_root.resolve()))
            session_dir = sessions_root / key / "session-test"
            session_dir.mkdir(parents=True)
            log_path = session_dir / "session.jsonl"
            event = {
                "type": "tool/call",
                "data": {"name": "read", "arguments": '{"file_path":"plan.md"}'},
            }
            log_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

            tailer = DshSessionLogTailer(project_root, since=0)
            with mock.patch(
                "functions.utils.executor.private_utils.dsh_session_stream.sessions_root",
                return_value=sessions_root,
            ):
                lines = tailer.poll()
            self.assertEqual(len(lines), 1)
            self.assertIn("[DSH tool] read", lines[0])


if __name__ == "__main__":
    unittest.main()
