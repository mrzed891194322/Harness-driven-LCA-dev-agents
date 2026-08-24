"""进程管理工具：身份记录、存活检测、精确终止、端口检查。"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .config import GUI_SCRIPT, PORT

# /proc/<pid>/comm 最长 16 字节；会话/显示管理器被误杀会导致图形会话注销。
_PROTECTED_COMM = frozenset(
    {
        "systemd",
        "init",
        "gnome-session",
        "gnome-session-b",
        "gnome-shell",
        "plasmashell",
        "kwin_x11",
        "kwin_wayland",
        "Xorg",
        "Xwayland",
        "gdm",
        "gdm-session-wor",
        "sddm",
        "lightdm",
        "dbus-daemon",
        "pipewire",
        "wireplumber",
        "explorer.exe",
        "winlogon.exe",
        "csrss.exe",
        "lsass.exe",
        "services.exe",
        "dwm.exe",
        "sihost.exe",
    }
)

_GUI_SCRIPT_MARKERS = (
    "src/gui/main.py",
    str(GUI_SCRIPT).replace("\\", "/").lower(),
    str(GUI_SCRIPT.resolve()).replace("\\", "/").lower(),
)

_PYTHON_OR_UV = re.compile(
    r"(?:^|[/\\s])(?:pythonw?(?:\d+(?:\.\d+)*)?|uv)(?:\.exe)?(?:\s|$)",
    re.I,
)

Record = dict[str, Any]
Target = dict[str, Any]


def _creation_flags() -> int:
    if sys.platform == "win32":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def comm_is_protected(comm: str) -> bool:
    """会话/显示相关进程名不得作为终止目标。"""
    return comm.strip().lower() in {name.lower() for name in _PROTECTED_COMM}


def cmdline_looks_like_gui(cmdline: str) -> bool:
    """命令行是否像本仓库 Gradio GUI（python/uv 启动 src/GUI/main.py）。"""
    normalized = cmdline.replace("\\", "/").lower()
    if not normalized.strip():
        return False
    if not any(marker in normalized for marker in _GUI_SCRIPT_MARKERS):
        return False
    return _PYTHON_OR_UV.search(cmdline) is not None


def _cmdline(pid: int) -> str:
    if pid <= 1:
        return ""
    if sys.platform == "win32":
        return _windows_cmdline(pid)
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\x00", b" ").decode("utf-8", "replace").strip()


def _windows_cmdline(pid: int) -> str:
    flags = _creation_flags()
    try:
        res = subprocess.run(
            ["wmic", "process", "where", f"ProcessId={pid}", "get", "CommandLine", "/value"],
            capture_output=True,
            text=True,
            creationflags=flags,
        )
        for line in res.stdout.splitlines():
            if line.lower().startswith("commandline="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    try:
        res = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine",
            ],
            capture_output=True,
            text=True,
            creationflags=flags,
        )
        return res.stdout.strip()
    except Exception:
        return ""


def _comm(pid: int) -> str:
    if pid <= 1:
        return ""
    if sys.platform == "win32":
        try:
            res = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                capture_output=True,
                text=True,
                creationflags=_creation_flags(),
            )
            line = res.stdout.strip().splitlines()[0] if res.stdout.strip() else ""
            if line.startswith('"'):
                return line.split('"', 2)[1]
        except Exception:
            return ""
        return ""
    try:
        return Path(f"/proc/{pid}/comm").read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _stat_fields(pid: int) -> list[str] | None:
    if pid <= 1 or sys.platform == "win32":
        return None
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    rest = stat[stat.rfind(")") + 2 :].split()
    return rest or None


def _ppid(pid: int) -> int:
    if sys.platform == "win32":
        return 0
    fields = _stat_fields(pid)
    if not fields:
        return 0
    try:
        return int(fields[1])
    except (IndexError, ValueError):
        return 0


def _pgid(pid: int) -> int | None:
    if sys.platform == "win32":
        return pid
    fields = _stat_fields(pid)
    if not fields or len(fields) < 3:
        return None
    try:
        return int(fields[2])
    except ValueError:
        return None


def _starttime(pid: int) -> int | str | None:
    """进程启动时刻。Linux 为 /proc stat 的 starttime，用于识别 PID 复用。"""
    if pid <= 1:
        return None
    if sys.platform == "win32":
        return _windows_starttime(pid)
    fields = _stat_fields(pid)
    if not fields or len(fields) < 20:
        return None
    try:
        return int(fields[19])
    except ValueError:
        return None


def _windows_starttime(pid: int) -> str | None:
    flags = _creation_flags()
    try:
        res = subprocess.run(
            ["wmic", "process", "where", f"ProcessId={pid}", "get", "CreationDate", "/value"],
            capture_output=True,
            text=True,
            creationflags=flags,
        )
        for line in res.stdout.splitlines():
            if line.lower().startswith("creationdate="):
                value = line.split("=", 1)[1].strip()
                return value or None
    except Exception:
        pass
    try:
        res = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CreationDate",
            ],
            capture_output=True,
            text=True,
            creationflags=flags,
        )
        value = res.stdout.strip()
        return value or None
    except Exception:
        return None


def snapshot_process(pid: int, role: str = "process") -> Target | None:
    """采集可用于事后核对的进程身份；采集失败则返回 None。"""
    if pid <= 1 or not is_process_alive(pid):
        return None
    starttime = _starttime(pid)
    if starttime is None:
        return None
    return {
        "pid": pid,
        "pgid": _pgid(pid),
        "starttime": starttime,
        "cmdline": _cmdline(pid),
        "comm": _comm(pid),
        "role": role,
    }


def _dedupe_targets(targets: list[Target]) -> list[Target]:
    seen: set[tuple[object, object]] = set()
    unique: list[Target] = []
    for target in targets:
        key = (target.get("pid"), target.get("starttime"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(target)
    return unique


def write_gui_record(path: Path, root_pid: int) -> Record | None:
    """把本次启动的 GUI 根进程及端口监听进程写入身份文件。"""
    root = snapshot_process(root_pid, role="root")
    if root is None:
        return None
    targets = [root]
    for listener_pid in port_listeners():
        snap = snapshot_process(listener_pid, role="listener")
        if snap is not None:
            targets.append(snap)
    record: Record = {
        "version": 1,
        "port": PORT,
        "script": str(GUI_SCRIPT),
        "root": root,
        "targets": _dedupe_targets(targets),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def refresh_gui_record(path: Path, record: Record) -> Record:
    """启动后补记已出现的端口监听进程，保持 starttime 等身份字段。"""
    targets = list(record.get("targets") or [])
    root = record.get("root")
    if isinstance(root, dict) and root not in targets:
        targets.insert(0, root)
    for listener_pid in port_listeners():
        snap = snapshot_process(listener_pid, role="listener")
        if snap is not None:
            targets.append(snap)
    record["targets"] = _dedupe_targets(targets)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def load_gui_record(path: Path) -> Record | None:
    """读取 GUI 身份文件；兼容旧版纯数字 PID。"""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    if text.isdigit():
        return {
            "version": 0,
            "port": PORT,
            "targets": [{"pid": int(text), "role": "root"}],
        }
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def record_targets(record: Record) -> list[Target]:
    targets = [item for item in (record.get("targets") or []) if isinstance(item, dict)]
    root = record.get("root")
    if isinstance(root, dict):
        targets = [root, *targets]
    return _dedupe_targets(targets)


def live_matches(target: Target) -> bool:
    """当前内核里的进程是否仍是记录中的同一个进程（防 PID 复用）。"""
    try:
        pid = int(target["pid"])
    except (KeyError, TypeError, ValueError):
        return False
    if pid <= 1 or not is_process_alive(pid):
        return False
    if comm_is_protected(_comm(pid)):
        return False
    recorded_start = target.get("starttime")
    if recorded_start is None:
        # 旧版只有 PID：没有 starttime 就不能证明不是复用，只能再核命令行。
        return is_gui_process(pid)
    live_start = _starttime(pid)
    if live_start is None:
        return False
    return str(live_start) == str(recorded_start)


def is_gui_process(pid: int) -> bool:
    """PID 是否为本仓库 GUI 进程（uv/python 运行 src/GUI/main.py）。"""
    if pid <= 1:
        return False
    if comm_is_protected(_comm(pid)):
        return False
    return cmdline_looks_like_gui(_cmdline(pid))


def resolve_gui_root(pid: int) -> int | None:
    """沿父进程向上找到 GUI 根进程；找不到则返回 None。"""
    gui_root: int | None = None
    current = pid
    seen: set[int] = set()
    for _ in range(32):
        if current <= 1 or current in seen:
            break
        seen.add(current)
        if is_gui_process(current):
            gui_root = current
        parent = _ppid(current)
        if parent <= 0 or parent == current:
            break
        current = parent
    return gui_root


def is_process_alive(pid: int) -> bool:
    """跨平台判断进程是否存活。PID 0/1 一律视为不可作为 GUI 目标。"""
    if pid <= 1:
        return False
    try:
        if sys.platform == "win32":
            res = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                creationflags=_creation_flags(),
            )
            return str(pid) in res.stdout
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _ancestor_pids() -> set[int]:
    ancestors: set[int] = set()
    current = os.getppid()
    for _ in range(64):
        if current <= 1:
            if current == 1:
                ancestors.add(1)
            break
        if current in ancestors:
            break
        ancestors.add(current)
        current = _ppid(current) if sys.platform != "win32" else 0
    return ancestors


def _children_of(pid: int) -> list[int]:
    if pid <= 1 or sys.platform == "win32":
        return []
    found: list[int] = []
    task_dir = Path(f"/proc/{pid}/task")
    try:
        for task in task_dir.iterdir():
            try:
                text = (task / "children").read_text(encoding="ascii", errors="replace").strip()
            except OSError:
                continue
            if text:
                for token in text.split():
                    try:
                        child = int(token)
                    except ValueError:
                        continue
                    if child > 1:
                        found.append(child)
        if found:
            return list(dict.fromkeys(found))
    except OSError:
        pass
    children: list[int] = []
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit():
                continue
            child = int(entry.name)
            if child > 1 and _ppid(child) == pid:
                children.append(child)
    except OSError:
        return []
    return children


def _collect_tree(root: int) -> list[int]:
    """收集 root 及其子孙，子孙在前、root 在后，便于先停子进程。"""
    ordered: list[int] = []
    stack = [root]
    seen: set[int] = set()
    while stack:
        pid = stack.pop()
        if pid <= 1 or pid in seen:
            continue
        seen.add(pid)
        ordered.append(pid)
        stack.extend(_children_of(pid))
    ordered.reverse()
    return ordered


def _terminate_pids(pids: list[int]) -> None:
    my_pid = os.getpid()
    ancestors = _ancestor_pids()
    targets = [pid for pid in pids if pid > 1 and pid != my_pid and pid not in ancestors]
    for pid in targets:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass
    deadline = time.monotonic() + 1.0
    remaining = [pid for pid in targets if is_process_alive(pid)]
    while remaining and time.monotonic() < deadline:
        time.sleep(0.05)
        remaining = [pid for pid in remaining if is_process_alive(pid)]
    for pid in remaining:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass


def _kill_pid_tree(pid: int) -> None:
    """只终止给定 PID 及其子孙，绝不 killpg。"""
    if pid <= 1 or pid == os.getpid() or pid in _ancestor_pids():
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            creationflags=_creation_flags(),
        )
        return
    _terminate_pids(_collect_tree(pid))


def kill_recorded_target(target: Target) -> bool:
    """仅在身份核对通过后终止该记录对应的进程树。"""
    if not live_matches(target):
        return False
    try:
        pid = int(target["pid"])
    except (KeyError, TypeError, ValueError):
        return False
    try:
        _kill_pid_tree(pid)
    except Exception:
        return False
    return True


def kill_process_tree(pid: int) -> None:
    """关闭已确认的 GUI 进程及其子进程。

    禁止对 PID<=1 或非 GUI 进程使用 killpg：`os.killpg(1, SIGTERM)` 等价于
    `kill -1`，会向当前用户几乎所有进程广播信号，表现为图形会话注销。
    """
    if pid <= 1 or pid == os.getpid():
        return
    if pid in _ancestor_pids():
        return
    if not is_gui_process(pid):
        return
    try:
        _kill_pid_tree(pid)
    except Exception:
        pass


def _parse_lsof_pids(output: str) -> list[int]:
    pids: list[int] = []
    for token in output.split():
        if token.strip().isdigit():
            pid = int(token.strip())
            if pid > 1:
                pids.append(pid)
    return list(dict.fromkeys(pids))


def _parse_netstat_pids(output: str, port: int) -> list[int]:
    pids: list[int] = []
    pattern = re.compile(rf":{port}(?:\s|$)")
    for line in output.splitlines():
        if "LISTENING" not in line.upper():
            continue
        if pattern.search(line) is None:
            continue
        parts = line.split()
        if not parts:
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid > 1:
            pids.append(pid)
    return list(dict.fromkeys(pids))


def port_listeners(port: int | None = None) -> list[int]:
    """返回占用目标端口的监听进程 PID 列表（不含 PID 0/1）。"""
    target = port if port is not None else PORT
    try:
        if sys.platform == "win32":
            res = subprocess.run(
                ["netstat", "-ano", "-p", "TCP"],
                capture_output=True,
                text=True,
                creationflags=_creation_flags(),
            )
            return _parse_netstat_pids(res.stdout, target)
        res = subprocess.run(
            ["lsof", "-t", f"-iTCP:{target}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
        )
        return _parse_lsof_pids(res.stdout)
    except Exception:
        return []


def is_gui_running(pid_file: Path) -> bool:
    """判断本仓库 GUI 是否正在运行（身份文件核对通过，或端口上确认为 GUI）。"""
    record = load_gui_record(pid_file)
    if record is not None:
        if any(live_matches(target) for target in record_targets(record)):
            return True
    return any(resolve_gui_root(pid) is not None for pid in port_listeners())


def resolve_pythonw(project_root: Path) -> str | None:
    """通过 uv run 解析虚拟环境的 pythonw.exe（GUI 子系统，无控制台窗口）。

    仅 Windows 适用；非 Windows 返回 None，由调用方回退到 uv run。
    """
    if sys.platform != "win32":
        return None
    try:
        res = subprocess.run(
            ["uv", "run", "python", "-c", "import sys; print(sys.executable)"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            creationflags=_creation_flags(),
        )
        py_exe = res.stdout.strip().replace("\\", "/")
        if py_exe.endswith("python.exe"):
            pyw = py_exe[: -len("python.exe")] + "pythonw.exe"
            if Path(pyw).exists():
                return pyw
    except Exception:
        pass
    return None
