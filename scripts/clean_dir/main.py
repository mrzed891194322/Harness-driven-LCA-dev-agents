#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent

try:
    from .config import CLEAN_TARGETS, PROJECT_ROOT
    from .utils.clean import clean_ignored_dir, parse_gitignore
except ImportError:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    from config import CLEAN_TARGETS, PROJECT_ROOT
    from utils.clean import clean_ignored_dir, parse_gitignore


def run_clean(dry_run: bool = False, yes: bool = False) -> int:
    """Clean ignored generated files according to configured .gitignore files."""
    print("=" * 60)
    print(f"项目根目录: {PROJECT_ROOT}")
    if dry_run:
        print("模式: [演练模式] (只显示，不实际删除文件)")
    print("=" * 60)

    if not yes and not dry_run:
        confirm = input(
            "警告：这将删除项目各个工作区被忽略目录中除例外项（如 README.md）以外的所有文件！\n确定要继续吗？(y/N): "
        )
        if confirm.strip().lower() not in ("y", "yes"):
            print("操作已取消。")
            return 0

    total_files = total_dirs = total_kept = total_failed = 0

    for target_cfg in CLEAN_TARGETS:
        name = target_cfg["name"]
        root_dir = target_cfg["path"]
        gitignore_path = target_cfg.get("gitignore") or root_dir / ".gitignore"

        if not gitignore_path.exists():
            continue

        ignored_dirs, keep_patterns = parse_gitignore(gitignore_path)
        if not ignored_dirs:
            continue

        print(f"\n开始清理 [{name}] 目录...")
        print(f"  忽略子目录: {', '.join(ignored_dirs)}")
        if keep_patterns:
            print(f"  例外保留: {', '.join(keep_patterns)}")

        for ignored in ignored_dirs:
            target_path = root_dir / ignored.replace("/**", "").strip("/")
            if not target_path.exists() or not target_path.is_dir():
                continue
            files, dirs, kept, failed = clean_ignored_dir(
                target_path,
                root_dir,
                PROJECT_ROOT,
                keep_patterns,
                dry_run=dry_run,
            )
            total_files += files
            total_dirs += dirs
            total_kept += kept
            total_failed += failed

    print("\n" + "=" * 60)
    if dry_run:
        print("演练结果统计：")
        print(f"- 预计删除文件数: {total_files}")
        print(f"- 预计删除空目录数: {total_dirs}")
        print(f"- 保留例外文件数: {total_kept}")
    else:
        print("清理完成！统计结果如下：")
        print(f"- 成功删除文件数: {total_files}")
        print(f"- 成功删除空目录数: {total_dirs}")
        print(f"- 保留例外文件数: {total_kept}")
        if total_failed > 0:
            print(f"- 删除失败数: {total_failed}")
    print("=" * 60)

    return 1 if total_failed > 0 else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="按指定的 .gitignore 规则清理项目中的生成及临时文件。")
    parser.add_argument("--dry-run", action="store_true", help="演练模式，仅打印将要删除的文件/目录")
    parser.add_argument("-y", "--yes", action="store_true", help="跳过二次确认，直接执行删除操作")
    args = parser.parse_args()
    raise SystemExit(run_clean(dry_run=args.dry_run, yes=args.yes))


if __name__ == "__main__":
    main()
