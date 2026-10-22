"""openLCA category cleanup (entities under the project category only).

Workspace files are cleared by the v5 runner at run start; this module only
removes foreground openLCA entities, holding the same
workspace/runs/_run/orchestrator.lock so it never races a live run.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from backend.settings import run_root
from harness.tools.shared.control_openlca.cleanup_service import run_openlca_clean

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)


class WorkspaceBusy(RuntimeError):
    pass


@contextmanager
def workspace_lock(workspace_root: Path) -> Iterator[None]:
    """Fail immediately if another orchestrator owns this workspace."""
    path = run_root(workspace_root) / "orchestrator.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            if path.stat().st_size == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise WorkspaceBusy(f"workspace busy: {workspace_root}") from exc
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise WorkspaceBusy(f"workspace busy: {workspace_root}") from exc
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    # Keep the lock file: unlinking it can let processes lock different inodes.


def run_clean(dry_run: bool = False, yes: bool = False) -> int:
    """Delete foreground openLCA entities under the project category."""
    print(f"项目根目录: {PROJECT_ROOT}")
    if dry_run:
        print("模式: [演练模式] (只预览，不删除)")
    if not yes and not dry_run:
        confirm = input("警告：这将删除 openLCA 项目分类下的前景实体！\n确定要继续吗？(y/N): ")
        if confirm.strip().lower() not in ("y", "yes"):
            print("操作已取消。")
            return 0
    workspace_root = PROJECT_ROOT / "workspace"
    try:
        with workspace_lock(workspace_root):
            ok, message, _details = run_openlca_clean(dry_run=dry_run)
    except WorkspaceBusy:
        print(f"[FAIL] workspace busy: {run_root(workspace_root) / 'orchestrator.lock'}", file=sys.stderr)
        return 1
    except (ValueError, OSError) as exc:
        print(f"[FAIL] openlca: {exc}", file=sys.stderr)
        return 1
    if not ok:
        print(f"[FAIL] openlca: {message}", file=sys.stderr)
        return 1
    print(f"  {message}")
    print("[OK] openlca clean completed")
    return 0


def cli_main(argv: list[str] | None = None) -> None:
    """Argparse entry for ``src/scripts/clean.py``."""
    import argparse

    parser = argparse.ArgumentParser(description="清理 openLCA 项目分类下的前景实体。")
    parser.add_argument("--dry-run", action="store_true", help="只预览将删除的实体数")
    parser.add_argument("-y", "--yes", action="store_true", help="跳过二次确认")
    args = parser.parse_args(argv)
    raise SystemExit(run_clean(dry_run=args.dry_run, yes=args.yes))
