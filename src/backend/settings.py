"""Backend settings and generic helpers (no domain rules).

Merged in P-1 from ``app_settings.py`` and ``utils/{env,filesystem,workspace_layout}.py``;
each former module is kept as its own section below.
"""

from __future__ import annotations

import fnmatch
import os
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Generic .env parse / upsert helpers (formerly utils/env.py)
# ---------------------------------------------------------------------------


def parse_env_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not path.is_file():
        return parsed
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed


def _format_env_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def upsert_env_keys(path: Path, updates: dict[str, str]) -> None:
    if path.is_file():
        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines(keepends=True)
    else:
        lines = []

    written: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                ending = "\n" if line.endswith("\n") else ""
                new_lines.append(f"{key}={_format_env_value(updates[key])}{ending}")
                written.add(key)
                continue
        new_lines.append(line)

    missing = [key for key in updates if key not in written]
    if missing:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        for key in missing:
            new_lines.append(f"{key}={_format_env_value(updates[key])}\n")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(new_lines), encoding="utf-8")


def remove_env_keys(path: Path, keys: set[str]) -> None:
    if not path.is_file() or not keys:
        return
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in keys:
                continue
        kept.append(line)
    path.write_text("".join(kept), encoding="utf-8")


# ---------------------------------------------------------------------------
# Generic filesystem clean helpers, no LCA / openLCA rules (formerly utils/filesystem.py)
# ---------------------------------------------------------------------------


class PathEscapeError(ValueError):
    """Raised when a clean target would leave the allowed root."""


def ensure_path_within(path: Path, allowed_root: Path) -> Path:
    """Return resolved path if it stays under allowed_root.

    Symlink targets that resolve outside ``allowed_root`` are rejected.
    The path itself may be a symlink; callers decide whether to unlink it
    without following.
    """
    allowed = allowed_root.resolve()
    try:
        resolved = path.resolve()
    except OSError as exc:
        raise PathEscapeError(f"cannot resolve path: {path}") from exc
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise PathEscapeError(
            f"path escapes allowed root: {path} -> {resolved} (root={allowed})"
        ) from exc
    return resolved


def parse_gitignore(gitignore_path: Path) -> tuple[list[str], list[str]]:
    """Parse ignored paths and exception patterns from a .gitignore file."""
    ignored_dirs: list[str] = []
    keep_patterns: list[str] = []

    if not gitignore_path.exists():
        return ignored_dirs, keep_patterns

    with open(gitignore_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("!"):
                keep_patterns.append(line[1:].strip())
                continue
            ignored_dirs.append(line)

    return ignored_dirs, keep_patterns


def match_keep(path: Path, base: Path, keep_patterns: list[str]) -> bool:
    """Return whether path matches any exception rule relative to base."""
    try:
        rel = path.relative_to(base).as_posix()
    except ValueError:
        return False

    for pattern in keep_patterns:
        pattern = pattern.strip("/")
        if rel == pattern:
            return True
        if "*" in pattern and fnmatch.fnmatch(rel, pattern):
            return True
        if rel.startswith(pattern + "/") or pattern.startswith(rel + "/"):
            return True
    return False


def _unlink_or_reject(
    path: Path,
    *,
    allowed_root: Path,
    project_root: Path,
    dry_run: bool,
    simulated_deleted: set[Path] | None = None,
) -> tuple[str, int, int, int]:
    """Delete one path safely. Returns (kind, files, dirs, failed)."""
    simulated = simulated_deleted if simulated_deleted is not None else set()
    try:
        display_path = path.relative_to(project_root)
    except ValueError:
        display_path = path

    if path.is_symlink():
        # Unlink the link itself; never follow into the target.
        if dry_run:
            print(f"  [待删除] 符号链接: {display_path}")
            simulated.add(path)
            return "symlink", 1, 0, 0
        try:
            path.unlink()
            print(f"  已删除符号链接: {display_path}")
            return "symlink", 1, 0, 0
        except Exception as exc:
            print(f"  删除符号链接失败: {path}，错误: {exc}", file=sys.stderr)
            return "symlink", 0, 0, 1

    try:
        ensure_path_within(path, allowed_root)
    except PathEscapeError as exc:
        print(f"  拒绝越界路径: {exc}", file=sys.stderr)
        return "escape", 0, 0, 1

    is_dir = path.is_dir()
    if dry_run:
        if is_dir:
            print(f"  [待删除] 目录: {display_path}")
            simulated.add(path)
            return "dir", 0, 1, 0
        print(f"  [待删除] 文件: {display_path}")
        simulated.add(path)
        return "file", 1, 0, 0

    try:
        if is_dir:
            shutil.rmtree(path)
            print(f"  已删除目录: {display_path}")
            return "dir", 0, 1, 0
        path.unlink()
        print(f"  已删除文件: {display_path}")
        return "file", 1, 0, 0
    except Exception as exc:
        kind = "目录" if is_dir else "文件"
        print(f"  删除{kind}失败: {path}，错误: {exc}", file=sys.stderr)
        return "error", 0, 0, 1


def clean_ignored_dir(
    dir_path: Path,
    base: Path,
    project_root: Path,
    keep_patterns: list[str],
    dry_run: bool = False,
    *,
    allowed_root: Path | None = None,
) -> tuple[int, int, int, int]:
    """Clean files under one ignored directory while preserving exception rules."""
    allowed = allowed_root or base
    deleted_files = 0
    deleted_dirs = 0
    kept_files = 0
    failed = 0
    simulated_deleted: set[Path] = set()

    # Do not follow a symlink that replaces the clean root itself.
    if dir_path.is_symlink() or not dir_path.exists():
        if dir_path.is_symlink():
            _kind, files, dirs, fail = _unlink_or_reject(
                dir_path,
                allowed_root=allowed,
                project_root=project_root,
                dry_run=dry_run,
                simulated_deleted=simulated_deleted,
            )
            return files, dirs, 0, fail
        return 0, 0, 0, 0

    try:
        ensure_path_within(dir_path, allowed)
    except PathEscapeError as exc:
        print(f"  拒绝越界清理根: {exc}", file=sys.stderr)
        return 0, 0, 0, 1

    for root, _dirs, files in os.walk(dir_path, topdown=False, followlinks=False):
        root_path = Path(root)

        for file in files:
            file_path = root_path / file
            if match_keep(file_path, base, keep_patterns):
                kept_files += 1
                continue
            _kind, files_n, dirs_n, fail_n = _unlink_or_reject(
                file_path,
                allowed_root=allowed,
                project_root=project_root,
                dry_run=dry_run,
                simulated_deleted=simulated_deleted,
            )
            deleted_files += files_n
            deleted_dirs += dirs_n
            failed += fail_n

        if root_path == dir_path:
            continue

        if root_path.is_symlink():
            _kind, files_n, dirs_n, fail_n = _unlink_or_reject(
                root_path,
                allowed_root=allowed,
                project_root=project_root,
                dry_run=dry_run,
                simulated_deleted=simulated_deleted,
            )
            deleted_files += files_n
            deleted_dirs += dirs_n
            failed += fail_n
            continue

        try:
            if dry_run:
                is_empty = all(
                    child in simulated_deleted for child in root_path.iterdir()
                )
            else:
                is_empty = not any(root_path.iterdir())
        except Exception:
            is_empty = False

        if not is_empty:
            continue

        try:
            display_path = root_path.relative_to(project_root)
        except ValueError:
            display_path = root_path

        if dry_run:
            print(f"  [待删除] 空目录: {display_path}")
            simulated_deleted.add(root_path)
            deleted_dirs += 1
            continue

        try:
            root_path.rmdir()
            deleted_dirs += 1
            print(f"  已删除空目录: {display_path}")
        except Exception as exc:
            failed += 1
            print(f"  删除目录失败: {root_path}，错误: {exc}", file=sys.stderr)

    return deleted_files, deleted_dirs, kept_files, failed


def clean_root_files(
    root_dir: Path,
    project_root: Path,
    keep_patterns: list[str],
    dry_run: bool = False,
    *,
    allowed_root: Path | None = None,
) -> tuple[int, int, int, int]:
    """Delete root-level files and subdirectories, preserving keep patterns."""
    deleted_files = 0
    deleted_dirs = 0
    kept_files = 0
    failed = 0
    allowed = allowed_root or root_dir

    if root_dir.is_symlink():
        _kind, files, dirs, fail = _unlink_or_reject(
            root_dir,
            allowed_root=allowed,
            project_root=project_root,
            dry_run=dry_run,
        )
        return files, dirs, 0, fail

    if not root_dir.exists() or not root_dir.is_dir():
        return deleted_files, deleted_dirs, kept_files, failed

    try:
        ensure_path_within(root_dir, allowed)
    except PathEscapeError as exc:
        print(f"  拒绝越界清理根: {exc}", file=sys.stderr)
        return 0, 0, 0, 1

    for child in sorted(root_dir.iterdir()):
        if match_keep(child, root_dir, keep_patterns):
            kept_files += 1
            continue
        _kind, files_n, dirs_n, fail_n = _unlink_or_reject(
            child,
            allowed_root=allowed,
            project_root=project_root,
            dry_run=dry_run,
        )
        deleted_files += files_n
        deleted_dirs += dirs_n
        failed += fail_n

    return deleted_files, deleted_dirs, kept_files, failed


# ---------------------------------------------------------------------------
# Canonical workspace subdirectory names (formerly utils/workspace_layout.py)
# ---------------------------------------------------------------------------

RECORDS_DIRNAME = "records"


def records_root(workspace_root: Path) -> Path:
    return workspace_root / RECORDS_DIRNAME


# ---------------------------------------------------------------------------
# Application-level settings keys loaded from the repository .env
# (formerly app_settings.py)
# ---------------------------------------------------------------------------

DEFAULT_HARNESS_AGENT = "pi"
HARNESS_AGENT_KEY = "HARNESS_AGENT"
GUI_PORT_KEY = "GUI_PORT"
OPENLCA_IPC_PORT_KEY = "OPENLCA_IPC_PORT"
GUI_LANG_KEY = "GUI_LANG"
DEFAULT_GUI_PORT = 7860
DEFAULT_OPENLCA_IPC_PORT = 8080
DEFAULT_GUI_LANG = "zh"
MIN_PORT = 1
MAX_PORT = 65535


def ensure_env_path(project_root: Path) -> Path:
    """Return the .env path, copying .env.example when the file is missing."""
    env_path = project_root / ".env"
    if env_path.is_file():
        return env_path
    example_path = project_root / ".env.example"
    if example_path.is_file():
        shutil.copy2(example_path, env_path)
        return env_path
    env_path.write_text("", encoding="utf-8")
    return env_path


def parse_port(value: object, default: int) -> int:
    """Parse a port number from env or UI input, falling back to default."""
    text = str(value or "").strip()
    if not text:
        return default
    try:
        port = int(text)
    except ValueError:
        return default
    if MIN_PORT <= port <= MAX_PORT:
        return port
    return default


def normalize_gui_lang(value: object) -> str:
    """Return a supported GUI locale code (zh or en)."""
    text = str(value or "").strip().lower()
    if text in ("en", "english", "en-us", "en_us"):
        return "en"
    return DEFAULT_GUI_LANG


def normalize_harness_agent(value: object) -> str:
    """Return a supported harness worker name, defaulting to Pi."""
    # Lazy import: backend.core imports backend.settings, so a module-level
    # import here would form a backend.core -> backend.settings -> backend.core cycle.
    from backend.core.agents.providers.registry import WORKERS as HARNESS_AGENTS

    agent = str(value or "").strip().lower()
    if agent in HARNESS_AGENTS:
        return agent
    return DEFAULT_HARNESS_AGENT


def load_port_settings(project_root: Path) -> dict[str, int]:
    """Load GUI and openLCA IPC port numbers from .env."""
    values = parse_env_file(project_root / ".env")
    return {
        "gui_port": parse_port(
            values.get(GUI_PORT_KEY) or os.getenv(GUI_PORT_KEY),
            DEFAULT_GUI_PORT,
        ),
        "openlca_ipc_port": parse_port(
            values.get(OPENLCA_IPC_PORT_KEY) or os.getenv(OPENLCA_IPC_PORT_KEY),
            DEFAULT_OPENLCA_IPC_PORT,
        ),
    }


def load_harness_agent(project_root: Path) -> str:
    """Return the persisted harness worker used by workflow launch."""
    values = parse_env_file(project_root / ".env")
    return normalize_harness_agent(
        values.get(HARNESS_AGENT_KEY) or os.getenv(HARNESS_AGENT_KEY)
    )
