# -*- coding: utf-8 -*-

import filecmp
import shutil
from pathlib import Path


SYNC_DIRECTIONS = ("upload-to-work", "work-to-upload", "bidirectional")


def is_readme(path: Path) -> bool:
    """
    Check if the file is a readme file (case-insensitive, contains 'readme').
    """
    return "readme" in path.name.lower()


def get_relative_files(dir_path: Path) -> set[Path]:
    """
    Recursively get all non-readme files, returning their relative paths to dir_path.
    """
    if not dir_path.exists() or not dir_path.is_dir():
        return set()
    
    files = set()
    for p in dir_path.rglob("*"):
        if p.is_file() and not is_readme(p):
            files.add(p.relative_to(dir_path))
    return files


def _files_are_equal(first: Path, second: Path) -> bool:
    """Return whether two files have identical contents."""
    try:
        return filecmp.cmp(first, second, shallow=False)
    except OSError:
        return False


def _copy_file(
    source: Path,
    target: Path,
    relative_path: Path,
    stat_key: str,
    source_label: str,
    target_label: str,
    stats: dict,
) -> None:
    """Copy one file and update the corresponding synchronization statistics."""
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        print(f"  Synced: {relative_path} : {source_label} -> {target_label}")
        stats[stat_key] += 1
    except Exception as e:
        print(
            f"  Failed to sync: {relative_path} "
            f"({source_label} -> {target_label}), error: {e}"
        )
        stats["errors"] += 1


def sync_directories(
    knowledge_dir: Path,
    input_dir: Path,
    direction: str = "bidirectional",
) -> dict:
    """
    Synchronize non-readme files in the requested direction.

    ``upload-to-work`` synchronizes workspace inputs to the harness knowledge
    source, while ``work-to-upload`` synchronizes in the reverse direction.
    The direction names are retained for CLI compatibility. Differing same-name
    files are overwritten from the selected source, while target-only files are
    left untouched. The default ``bidirectional`` mode uses modification time.
    """
    if direction not in SYNC_DIRECTIONS:
        raise ValueError(
            f"Unsupported sync direction {direction!r}; "
            f"expected one of: {', '.join(SYNC_DIRECTIONS)}"
        )

    stats = {
        "copied_a_to_b": 0,
        "copied_b_to_a": 0,
        "in_sync": 0,
        "errors": 0,
        "ignored": 0,
    }

    # Ensure directories exist
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)

    # Count ignored readme files
    readme_count = 0
    for d in (knowledge_dir, input_dir):
        if d.exists():
            for p in d.rglob("*"):
                if p.is_file() and is_readme(p):
                    readme_count += 1
    stats["ignored"] = readme_count

    if direction == "upload-to-work":
        source_dir = input_dir
        target_dir = knowledge_dir
        stat_key = "copied_b_to_a"
        source_label = "input_dir"
        target_label = "knowledge_dir"
        for rel_path in sorted(get_relative_files(source_dir)):
            source_path = source_dir / rel_path
            target_path = target_dir / rel_path

            if target_path.is_file() and _files_are_equal(source_path, target_path):
                stats["in_sync"] += 1
                continue

            _copy_file(
                source_path,
                target_path,
                rel_path,
                stat_key,
                source_label,
                target_label,
                stats,
            )
        return stats

    if direction == "work-to-upload":
        source_dir = knowledge_dir
        target_dir = input_dir
        stat_key = "copied_a_to_b"
        source_label = "knowledge_dir"
        target_label = "input_dir"
        for rel_path in sorted(get_relative_files(source_dir)):
            source_path = source_dir / rel_path
            target_path = target_dir / rel_path

            if target_path.is_file() and _files_are_equal(source_path, target_path):
                stats["in_sync"] += 1
                continue

            _copy_file(
                source_path,
                target_path,
                rel_path,
                stat_key,
                source_label,
                target_label,
                stats,
            )
        return stats

    # Get relative paths of all non-readme files for bidirectional mode.
    files_work = get_relative_files(knowledge_dir)
    files_upload = get_relative_files(input_dir)
    all_files = files_work.union(files_upload)

    for rel_path in sorted(all_files):
        work_path = knowledge_dir / rel_path
        upload_path = input_dir / rel_path

        exists_work = work_path.exists() and work_path.is_file()
        exists_upload = upload_path.exists() and upload_path.is_file()

        action = None

        if exists_work and not exists_upload:
            action = "copy_a_to_b"
        elif exists_upload and not exists_work:
            action = "copy_b_to_a"
        elif exists_work and exists_upload:
            mtime_work = work_path.stat().st_mtime
            mtime_upload = upload_path.stat().st_mtime
            
            # Use 0.001s tolerance for mtime comparison
            if abs(mtime_work - mtime_upload) < 0.001:
                action = "in_sync"
            elif mtime_work > mtime_upload:
                action = "copy_a_to_b"
            else:
                action = "copy_b_to_a"

        if action == "copy_a_to_b":
            _copy_file(
                work_path,
                upload_path,
                rel_path,
                "copied_a_to_b",
                "knowledge_dir",
                "input_dir",
                stats,
            )

        elif action == "copy_b_to_a":
            _copy_file(
                upload_path,
                work_path,
                rel_path,
                "copied_b_to_a",
                "input_dir",
                "knowledge_dir",
                stats,
            )

        elif action == "in_sync":
            stats["in_sync"] += 1

    return stats
