import shutil
import uuid
from pathlib import Path


def new_staging_dir(output_dir: Path) -> Path:
    """Create a unique build directory beside the live database."""
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = output_dir.parent / f".{output_dir.name}.staging-{uuid.uuid4().hex}"
    staging_dir.mkdir(parents=False, exist_ok=False)
    return staging_dir


def discard_staging(staging_dir: Path) -> None:
    """Remove a failed or abandoned staged build."""
    if staging_dir.exists():
        shutil.rmtree(staging_dir)


def swap_staged_output(staging_dir: Path, output_dir: Path) -> None:
    """Replace the live database and roll back if the staged rename fails."""
    backup_dir = output_dir.parent / f".{output_dir.name}.backup-{uuid.uuid4().hex}"
    moved_existing = False
    try:
        if output_dir.exists():
            output_dir.rename(backup_dir)
            moved_existing = True
        staging_dir.rename(output_dir)
    except Exception:
        if moved_existing and backup_dir.exists() and not output_dir.exists():
            backup_dir.rename(output_dir)
        raise
    else:
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
