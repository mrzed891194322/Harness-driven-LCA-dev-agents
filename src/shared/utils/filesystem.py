"""Generic filesystem clean helpers (no LCA / openLCA rules)."""

from __future__ import annotations

import fnmatch
import os
import shutil
import sys
from pathlib import Path


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
