# -*- coding: utf-8 -*-

import shutil
from pathlib import Path

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

def sync_directories(work_dir: Path, user_upload: Path) -> dict:
    """
    Bidirectional file synchronization logic:
    1. Compute the union of relative paths for all non-readme files in work_dir and user_upload.
    2. For each relative path:
       - If it only exists in work_dir: copy to user_upload.
       - If it only exists in user_upload: copy to work_dir.
       - If it exists in both: compare modification times (mtime), overwrite the older one with the newer one.
    3. Preserve modification time metadata using shutil.copy2 for subsequent incremental syncs.
    """
    stats = {
        "copied_a_to_b": 0,
        "copied_b_to_a": 0,
        "in_sync": 0,
        "errors": 0,
        "ignored": 0,
    }

    # Ensure directories exist
    work_dir.mkdir(parents=True, exist_ok=True)
    user_upload.mkdir(parents=True, exist_ok=True)

    # Get relative paths of all non-readme files
    files_work = get_relative_files(work_dir)
    files_upload = get_relative_files(user_upload)
    all_files = files_work.union(files_upload)

    # Count ignored readme files
    readme_count = 0
    for d in (work_dir, user_upload):
        if d.exists():
            for p in d.rglob("*"):
                if p.is_file() and is_readme(p):
                    readme_count += 1
    stats["ignored"] = readme_count

    for rel_path in sorted(all_files):
        work_path = work_dir / rel_path
        upload_path = user_upload / rel_path

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
            try:
                upload_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(work_path, upload_path)
                print(f"  Synced: {rel_path} : work_dir -> user_upload")
                stats["copied_a_to_b"] += 1
            except Exception as e:
                print(f"  Failed to sync: {rel_path} (work_dir -> user_upload), error: {e}")
                stats["errors"] += 1

        elif action == "copy_b_to_a":
            try:
                work_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(upload_path, work_path)
                print(f"  Synced: {rel_path} : user_upload -> work_dir")
                stats["copied_b_to_a"] += 1
            except Exception as e:
                print(f"  Failed to sync: {rel_path} (user_upload -> work_dir), error: {e}")
                stats["errors"] += 1

        elif action == "in_sync":
            stats["in_sync"] += 1

    return stats
