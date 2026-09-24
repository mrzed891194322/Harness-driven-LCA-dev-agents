from __future__ import annotations

import unittest

from core.agents.turn_transport import WorkerTransportError, detect_worker_transport_failure


class TurnTransportTests(unittest.TestCase):
    def test_pi_connection_error_without_progress(self) -> None:
        stdout = (
            '{"type":"turn_end","message":{"role":"assistant","stopReason":"error",'
            '"errorMessage":"Connection error."}}\n'
        )
        detail = detect_worker_transport_failure("pi", stdout)
        self.assertEqual(detail, "Connection error.")

    def test_pi_ignored_when_tool_progress(self) -> None:
        stdout = (
            '{"type":"tool_execution_end","toolName":"read"}\n'
            '{"type":"turn_end","message":{"role":"assistant","stopReason":"error",'
            '"errorMessage":"Connection error."}}\n'
        )
        self.assertIsNone(detect_worker_transport_failure("pi", stdout))

    def test_pi_auto_retry_end(self) -> None:
        stdout = '{"type":"auto_retry_end","success":false,"finalError":"Connection error."}\n'
        self.assertEqual(
            detect_worker_transport_failure("pi", stdout), "Connection error."
        )

    def test_codex_turn_failed(self) -> None:
        stdout = '{"type":"turn.failed","error":"rate limit exceeded"}\n'
        self.assertIn("rate limit", detect_worker_transport_failure("codex", stdout) or "")

    def test_codex_ignored_with_agent_message(self) -> None:
        stdout = (
            '{"type":"item.completed","item":{"type":"agent_message","text":"done"}}\n'
            '{"type":"turn.failed","error":"ignored"}\n'
        )
        self.assertIsNone(detect_worker_transport_failure("codex", stdout))

    def test_claude_result_error(self) -> None:
        stdout = '{"type":"result","is_error":true,"result":"authentication failed"}\n'
        self.assertIn(
            "authentication",
            detect_worker_transport_failure("claude", stdout) or "",
        )

    def test_claude_ignored_with_tool_use(self) -> None:
        stdout = (
            '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read"}]}}\n'
            '{"type":"result","is_error":true,"result":"x"}\n'
        )
        self.assertIsNone(detect_worker_transport_failure("claude", stdout))

    def test_opencode_error_event(self) -> None:
        stdout = '{"type":"error","message":"502 Bad Gateway"}\n'
        self.assertIn("502", detect_worker_transport_failure("opencode", stdout) or "")

    def test_shared_stderr_heuristic(self) -> None:
        stderr = "curl: (7) Failed to connect: Connection refused\n"
        self.assertIsNotNone(detect_worker_transport_failure("codex", "", stderr))

    def test_worker_transport_error_type(self) -> None:
        err = WorkerTransportError("pi 模型连接失败：Connection error.")
        self.assertIn("Connection error", str(err))


if __name__ == "__main__":
    unittest.main()
