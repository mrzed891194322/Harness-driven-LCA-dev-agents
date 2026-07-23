import os
import tempfile
import unittest
from pathlib import Path

from scripts.file_sync.main import parse_args
from scripts.file_sync.utils.sync import sync_directories


class SyncDirectoriesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.work_dir = root / "workspace"
        self.upload_dir = root / "uploads"
        self.work_dir.mkdir()
        self.upload_dir.mkdir()

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_upload_to_work_uses_upload_as_authoritative_source(self):
        self.write(self.upload_dir / "new.txt", "from upload")
        self.write(self.upload_dir / "nested" / "conflict.txt", "upload version")
        self.write(self.work_dir / "only-in-work.txt", "keep me")
        self.write(self.work_dir / "nested" / "conflict.txt", "old work version")
        self.write(self.upload_dir / "README.md", "ignored")
        self.write(self.work_dir / "README.md", "ignored")

        stats = sync_directories(
            self.work_dir,
            self.upload_dir,
            direction="upload-to-work",
        )

        self.assertEqual((self.work_dir / "new.txt").read_text(), "from upload")
        self.assertEqual(
            (self.work_dir / "nested" / "conflict.txt").read_text(),
            "upload version",
        )
        self.assertTrue((self.work_dir / "only-in-work.txt").exists())
        self.assertEqual((self.work_dir / "README.md").read_text(), "ignored")
        self.assertEqual(stats["copied_b_to_a"], 2)
        self.assertEqual(stats["copied_a_to_b"], 0)
        self.assertEqual(stats["ignored"], 2)

    def test_work_to_upload_uses_work_as_authoritative_source(self):
        self.write(self.work_dir / "new.json", "from work")
        self.write(self.work_dir / "nested" / "conflict.json", "work version")
        self.write(self.upload_dir / "only-in-upload.json", "keep me")
        self.write(self.upload_dir / "nested" / "conflict.json", "old upload version")

        stats = sync_directories(
            self.work_dir,
            self.upload_dir,
            direction="work-to-upload",
        )

        self.assertEqual((self.upload_dir / "new.json").read_text(), "from work")
        self.assertEqual(
            (self.upload_dir / "nested" / "conflict.json").read_text(),
            "work version",
        )
        self.assertTrue((self.upload_dir / "only-in-upload.json").exists())
        self.assertEqual(stats["copied_a_to_b"], 2)
        self.assertEqual(stats["copied_b_to_a"], 0)

    def test_bidirectional_default_preserves_mtime_behavior(self):
        work_file = self.work_dir / "same.txt"
        upload_file = self.upload_dir / "same.txt"
        self.write(work_file, "work version")
        self.write(upload_file, "upload version")
        os.utime(work_file, (200, 200))
        os.utime(upload_file, (100, 100))

        stats = sync_directories(self.work_dir, self.upload_dir)

        self.assertEqual(upload_file.read_text(), "work version")
        self.assertEqual(stats["copied_a_to_b"], 1)

    def test_invalid_direction_is_rejected(self):
        with self.assertRaises(ValueError):
            sync_directories(self.work_dir, self.upload_dir, direction="invalid")


class FileSyncCliTests(unittest.TestCase):
    def test_direction_defaults_to_bidirectional(self):
        self.assertEqual(parse_args([]).direction, "bidirectional")

    def test_direction_is_parsed(self):
        self.assertEqual(
            parse_args(["--direction", "upload-to-work"]).direction,
            "upload-to-work",
        )


if __name__ == "__main__":
    unittest.main()
