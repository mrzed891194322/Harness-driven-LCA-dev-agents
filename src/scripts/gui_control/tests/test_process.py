from __future__ import annotations

import json
import signal
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

GUI_CONTROL_DIR = Path(__file__).resolve().parents[1]
if str(GUI_CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(GUI_CONTROL_DIR))

from utils import process as process_mod  # noqa: E402
from utils.process import (  # noqa: E402
    cmdline_looks_like_gui,
    is_gui_running,
    is_process_alive,
    kill_process_tree,
    kill_recorded_target,
    live_matches,
    load_gui_record,
    record_targets,
    write_gui_record,
)
from stop_gui import stop_gui  # noqa: E402


class CmdlineIdentityTests(unittest.TestCase):
    def test_accepts_uv_or_python_gui_entry(self) -> None:
        self.assertTrue(
            cmdline_looks_like_gui("uv run python -u /repo/src/GUI/main.py")
        )
        self.assertTrue(
            cmdline_looks_like_gui("/venv/bin/python -u /repo/src/GUI/main.py")
        )

    def test_rejects_editor_or_unrelated_commands(self) -> None:
        self.assertFalse(cmdline_looks_like_gui("vim src/GUI/main.py"))
        self.assertFalse(cmdline_looks_like_gui("/usr/lib/systemd/systemd --user"))
        self.assertFalse(cmdline_looks_like_gui("gnome-shell"))


class ProcessRecordTests(unittest.TestCase):
    def test_load_legacy_plain_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "gui.pid"
            path.write_text("4321\n", encoding="utf-8")
            record = load_gui_record(path)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["version"], 0)
        self.assertEqual(record_targets(record)[0]["pid"], 4321)

    def test_write_record_keeps_starttime(self) -> None:
        snapshot = {
            "pid": 2222,
            "pgid": 2222,
            "starttime": 999,
            "cmdline": "uv run python -u src/GUI/main.py",
            "comm": "uv",
            "role": "root",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "gui.pid"
            with patch.object(process_mod, "snapshot_process", return_value=snapshot), patch.object(
                process_mod, "port_listeners", return_value=[]
            ):
                record = write_gui_record(path, 2222)
            raw = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsNotNone(record)
        self.assertEqual(raw["root"]["pid"], 2222)
        self.assertEqual(raw["root"]["starttime"], 999)


class LiveMatchTests(unittest.TestCase):
    def test_pid_reuse_without_matching_starttime_is_rejected(self) -> None:
        target = {"pid": 100, "starttime": 111}
        with patch.object(process_mod, "is_process_alive", return_value=True), patch.object(
            process_mod, "_comm", return_value="python"
        ), patch.object(process_mod, "_starttime", return_value=222):
            self.assertFalse(live_matches(target))

    def test_matching_starttime_is_accepted(self) -> None:
        target = {"pid": 100, "starttime": 111}
        with patch.object(process_mod, "is_process_alive", return_value=True), patch.object(
            process_mod, "_comm", return_value="python"
        ), patch.object(process_mod, "_starttime", return_value=111):
            self.assertTrue(live_matches(target))

    def test_legacy_pid_without_starttime_requires_gui_cmdline(self) -> None:
        target = {"pid": 100}
        with patch.object(process_mod, "is_process_alive", return_value=True), patch.object(
            process_mod, "_comm", return_value="python"
        ), patch.object(process_mod, "is_gui_process", return_value=False):
            self.assertFalse(live_matches(target))


class KillSafetyTests(unittest.TestCase):
    def test_pid_one_never_signaled(self) -> None:
        with patch.object(process_mod.os, "kill") as mock_kill, patch.object(
            process_mod.os, "killpg", create=True
        ) as mock_killpg:
            kill_process_tree(1)
            kill_process_tree(0)
        mock_kill.assert_not_called()
        mock_killpg.assert_not_called()

    def test_recorded_kill_skipped_on_identity_mismatch(self) -> None:
        target = {"pid": 100, "starttime": 1}
        with patch.object(process_mod, "live_matches", return_value=False), patch.object(
            process_mod, "_kill_pid_tree"
        ) as mock_kill:
            self.assertFalse(kill_recorded_target(target))
            mock_kill.assert_not_called()

    def test_unix_tree_kill_never_uses_killpg(self) -> None:
        with patch.object(process_mod, "is_gui_process", return_value=True), patch.object(
            process_mod, "_ancestor_pids", return_value=set()
        ), patch.object(process_mod, "_collect_tree", return_value=[222, 111]), patch.object(
            process_mod, "is_process_alive", return_value=False
        ), patch.object(process_mod.sys, "platform", "linux"), patch.object(
            process_mod.os, "kill"
        ) as mock_kill, patch.object(process_mod.os, "killpg", create=True) as mock_killpg:
            kill_process_tree(111)
        mock_killpg.assert_not_called()
        mock_kill.assert_any_call(222, signal.SIGTERM)
        mock_kill.assert_any_call(111, signal.SIGTERM)

    def test_lsof_parser_drops_pid_one(self) -> None:
        self.assertEqual(process_mod._parse_lsof_pids("1\n7860\n1 4321"), [7860, 4321])

    def test_netstat_parser_requires_exact_port(self) -> None:
        output = "\n".join(
            [
                "TCP    127.0.0.1:7860     0.0.0.0:0    LISTENING    111",
                "TCP    127.0.0.1:17860    0.0.0.0:0    LISTENING    222",
                "TCP    127.0.0.1:78601    0.0.0.0:0    LISTENING    333",
            ]
        )
        self.assertEqual(process_mod._parse_netstat_pids(output, 7860), [111])


class GuiRunningTests(unittest.TestCase):
    def test_stale_record_with_reused_pid_is_not_running(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "gui.pid"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "targets": [{"pid": 100, "starttime": 1, "role": "root"}],
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(process_mod, "live_matches", return_value=False), patch.object(
                process_mod, "port_listeners", return_value=[]
            ):
                self.assertFalse(is_gui_running(path))


class AliveGuardTests(unittest.TestCase):
    def test_pid_zero_and_one_are_not_alive(self) -> None:
        self.assertFalse(is_process_alive(0))
        self.assertFalse(is_process_alive(1))


class StopGuiRecordTests(unittest.TestCase):
    def test_stale_identity_does_not_kill(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "gui.pid"
            path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "targets": [{"pid": 100, "starttime": 1, "role": "root"}],
                    }
                ),
                encoding="utf-8",
            )
            with patch("stop_gui.PID_FILE", path), patch(
                "stop_gui.kill_recorded_target", return_value=False
            ) as mock_kill_recorded, patch(
                "stop_gui.port_listeners", return_value=[]
            ), patch("stop_gui.kill_process_tree") as mock_tree:
                stopped = stop_gui()
            self.assertFalse(stopped)
            mock_kill_recorded.assert_called_once()
            mock_tree.assert_not_called()
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
