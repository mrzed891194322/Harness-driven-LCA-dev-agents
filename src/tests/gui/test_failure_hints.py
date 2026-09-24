from __future__ import annotations

import unittest

from gui.functions.openlca_failure_hints import (
    maybe_append_handoff_failure_hint,
    maybe_append_worker_transport_hint,
    should_show_handoff_failure_hint,
    should_show_worker_transport_hint,
)


class FailureHintTests(unittest.TestCase):
    def test_transport_and_handoff_hints_are_mutually_exclusive(self) -> None:
        manifest = {
            "status_reason": (
                "worker 模型连接失败（01-intake-gate.reviewer，agent=pi）：x"
            ),
            "run_id": "abc",
        }
        self.assertTrue(should_show_worker_transport_hint(manifest))
        self.assertFalse(should_show_handoff_failure_hint(manifest))

    def test_handoff_hint_when_not_transport(self) -> None:
        manifest = {
            "status_reason": "handoff 无效：x records/handoffs/y.json: missing",
        }
        self.assertFalse(should_show_worker_transport_hint(manifest))
        self.assertTrue(should_show_handoff_failure_hint(manifest))

    def test_append_worker_transport_hint(self) -> None:
        from pathlib import Path

        manifest = {
            "status_reason": "worker 模型连接失败（a，agent=codex）：err",
            "run_id": "r1",
        }
        body = "### 失败原因\n\n- err\n"
        out = maybe_append_worker_transport_hint(Path("/tmp/ws"), manifest, body)
        self.assertIn("Worker 模型连接失败", out)
        self.assertIn("CODEX_MODEL", out)
        out2 = maybe_append_handoff_failure_hint(Path("/tmp/ws"), manifest, out)
        self.assertNotIn("handoff 交卷失败", out2)


if __name__ == "__main__":
    unittest.main()
