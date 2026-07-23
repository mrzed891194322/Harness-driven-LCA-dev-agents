import fnmatch
import os
import sys
from pathlib import Path


def parse_gitignore(gitignore_path: Path) -> tuple[list[str], list[str]]:
    """Parse ignored paths and exception patterns from a .gitignore file."""
    ignored_dirs: list[str] = []
    keep_patterns: list[str] = []

    if not gitignore_path.exists():
        return ignored_dirs, keep_patterns

    with open(gitignore_path, "r", encoding="utf-8") as f:
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


def clean_ignored_dir(
    dir_path: Path,
    base: Path,
    project_root: Path,
    keep_patterns: list[str],
    dry_run: bool = False,
) -> tuple[int, int, int, int]:
    """Clean files under one ignored directory while preserving exception rules."""
    deleted_files = 0
    deleted_dirs = 0
    kept_files = 0
    failed = 0
    simulated_deleted: set[Path] = set()

    for root, _dirs, files in os.walk(dir_path, topdown=False):
        root_path = Path(root)

        for file in files:
            file_path = root_path / file
            if match_keep(file_path, base, keep_patterns):
                kept_files += 1
                continue
            try:
                display_path = file_path.relative_to(project_root)
            except ValueError:
                display_path = file_path

            if dry_run:
                print(f"  [待删除] 文件: {display_path}")
                simulated_deleted.add(file_path)
                deleted_files += 1
                continue

            try:
                file_path.unlink()
                deleted_files += 1
                print(f"  已删除文件: {display_path}")
            except Exception as exc:
                failed += 1
                print(f"  删除文件失败: {file_path}，错误: {exc}", file=sys.stderr)

        if root_path == dir_path:
            continue

        try:
            if dry_run:
                is_empty = all(child in simulated_deleted for child in root_path.iterdir())
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
