"""Tests for GUI file_sync."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import support  # noqa: F401,E402

from functions.file_sync.main import sync_files  # noqa: E402


class FileSyncTests(unittest.TestCase):
    def test_sync_knowledge_copies_uploads(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            knowledge = root / "harness" / "knowledge"
            knowledge.mkdir(parents=True)
            source = root / "uploads" / "note.txt"
            source.parent.mkdir(parents=True)
            source.write_text("hello", encoding="utf-8")

            with patch("config.KNOWLEDGE_DIR", knowledge):
                result = sync_files("knowledge", uploads=str(source))

            self.assertTrue(result.ok)
            self.assertTrue((knowledge / "note.txt").exists())

    def test_sync_knowledge_allows_empty_uploads(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            knowledge = Path(temp) / "knowledge"
            knowledge.mkdir(parents=True)

            with patch("config.KNOWLEDGE_DIR", knowledge):
                result = sync_files("knowledge", uploads=None)

            self.assertTrue(result.ok)
            self.assertIn("no uploaded", result.message)

    def test_sync_plan_writes_workspace_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plan_path = Path(temp) / "workspace" / "inputs" / "plan.md"
            plan_path.parent.mkdir(parents=True)
            text = "# Plan\n\nbody only\n"

            result = sync_files(
                "plan",
                values=[],
                source_text=text,
                target_path=plan_path,
            )

            self.assertTrue(result.ok)
            self.assertEqual(plan_path.read_text(encoding="utf-8"), text)

    def test_sync_plan_requires_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plan_path = Path(temp) / "plan.md"
            result = sync_files(
                "plan",
                values=[],
                source_text="",
                target_path=plan_path,
            )
            self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()
