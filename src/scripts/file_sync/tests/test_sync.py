import os
import tempfile
import unittest
from pathlib import Path

from src.scripts.file_sync.config import PROJECT_ROOT, SYNC_TARGETS
from src.scripts.file_sync.main import parse_args
from src.scripts.file_sync.utils.sync import sync_directories


class SyncDirectoriesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.knowledge_dir = root / "knowledge"
        self.input_dir = root / "inputs"
        self.knowledge_dir.mkdir()
        self.input_dir.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_upload_to_work_uses_upload_as_authoritative_source(self):
        self.write(self.input_dir / "new.txt", "from input")
        self.write(self.input_dir / "nested" / "conflict.txt", "input version")
        self.write(self.knowledge_dir / "only-in-work.txt", "keep me")
        self.write(self.knowledge_dir / "nested" / "conflict.txt", "old work version")
        self.write(self.input_dir / "README.md", "ignored")
        self.write(self.knowledge_dir / "README.md", "ignored")

        stats = sync_directories(
            self.knowledge_dir,
            self.input_dir,
            direction="upload-to-work",
        )

        self.assertEqual((self.knowledge_dir / "new.txt").read_text(), "from input")
        self.assertEqual(
            (self.knowledge_dir / "nested" / "conflict.txt").read_text(),
            "input version",
        )
        self.assertTrue((self.knowledge_dir / "only-in-work.txt").exists())
        self.assertEqual((self.knowledge_dir / "README.md").read_text(), "ignored")
        self.assertEqual(stats["copied_b_to_a"], 2)
        self.assertEqual(stats["copied_a_to_b"], 0)
        self.assertEqual(stats["ignored"], 2)

    def test_work_to_upload_uses_work_as_authoritative_source(self):
        self.write(self.knowledge_dir / "new.json", "from knowledge")
        self.write(self.knowledge_dir / "nested" / "conflict.json", "knowledge version")
        self.write(self.input_dir / "only-in-input.json", "keep me")
        self.write(self.input_dir / "nested" / "conflict.json", "old input version")

        stats = sync_directories(
            self.knowledge_dir,
            self.input_dir,
            direction="work-to-upload",
        )

        self.assertEqual((self.input_dir / "new.json").read_text(), "from knowledge")
        self.assertEqual(
            (self.input_dir / "nested" / "conflict.json").read_text(),
            "knowledge version",
        )
        self.assertTrue((self.input_dir / "only-in-input.json").exists())
        self.assertEqual(stats["copied_a_to_b"], 2)
        self.assertEqual(stats["copied_b_to_a"], 0)

    def test_bidirectional_default_preserves_mtime_behavior(self):
        work_file = self.knowledge_dir / "same.txt"
        upload_file = self.input_dir / "same.txt"
        self.write(work_file, "work version")
        self.write(upload_file, "upload version")
        os.utime(work_file, (200, 200))
        os.utime(upload_file, (100, 100))

        stats = sync_directories(self.knowledge_dir, self.input_dir)

        self.assertEqual(upload_file.read_text(), "work version")
        self.assertEqual(stats["copied_a_to_b"], 1)

    def test_invalid_direction_is_rejected(self):
        with self.assertRaises(ValueError):
            sync_directories(self.knowledge_dir, self.input_dir, direction="invalid")


class FileSyncCliTests(unittest.TestCase):
    def test_targets_use_workspace_reference_inputs(self):
        self.assertEqual(
            {target["name"] for target in SYNC_TARGETS},
            {"reference_file", "reference_data"},
        )
        for target in SYNC_TARGETS:
            self.assertTrue(
                target["input_dir"].is_relative_to(
                    PROJECT_ROOT / "workspace" / "inputs" / "references"
                )
            )
            self.assertTrue(
                target["knowledge_dir"].is_relative_to(
                    PROJECT_ROOT
                    / "harness"
                    / "knowledge"
                    / "inputs"
                    / "user_ref"
                )
            )

    def test_direction_defaults_to_bidirectional(self):
        self.assertEqual(parse_args([]).direction, "bidirectional")

    def test_direction_is_parsed(self):
        self.assertEqual(
            parse_args(["--direction", "upload-to-work"]).direction,
            "upload-to-work",
        )


if __name__ == "__main__":
    unittest.main()
