#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
项目清理入口脚本

功能：
    根据配置中的目标目录，解析其对应的 .gitignore 文件，清理被忽略的文件和空子目录，并保留例外项。

使用方式：
    # 交互确认后执行清理
    uv run python scripts/clean_dir/main.py

    # 演练模式，仅打印不删除
    uv run python scripts/clean_dir/main.py --dry-run

    # 跳过确认直接执行
    uv run python scripts/clean_dir/main.py -y
"""

import sys
import argparse
from pathlib import Path

# 将本脚本所在目录加入 sys.path 以便导入同目录模块
SCRIPT_DIR = Path(__file__).parent
sys.path.append(str(SCRIPT_DIR))

from config import CLEAN_TARGETS, PROJECT_ROOT
from utils.clean import parse_gitignore, clean_ignored_dir


def main():
    parser = argparse.ArgumentParser(
        description="按指定的 .gitignore 规则清理项目中的生成及临时文件。"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="演练模式，仅打印将要删除的文件/目录，不执行实际删除"
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="跳过二次确认，直接执行删除操作"
    )
    args = parser.parse_args()

    print("=" * 60)
    print(f"项目根目录: {PROJECT_ROOT}")
    if args.dry_run:
        print("模式: [演练模式] (只显示，不实际删除文件)")
    print("=" * 60)

    # 二次确认
    if not args.yes and not args.dry_run:
        confirm = input(
            "警告：这将删除项目各个工作区被忽略目录中除例外项（如 README.md）以外的所有文件！\n确定要继续吗？(y/N): "
        )
        if confirm.strip().lower() not in ("y", "yes"):
            print("操作已取消。")
            sys.exit(0)

    total_files = total_dirs = total_kept = total_failed = 0

    for target_cfg in CLEAN_TARGETS:
        name = target_cfg["name"]
        root_dir = target_cfg["path"]
        gitignore_path = target_cfg.get("gitignore")

        if not gitignore_path:
            gitignore_path = root_dir / ".gitignore"

        if not gitignore_path.exists():
            continue

        ignored_dirs, keep_patterns = parse_gitignore(gitignore_path)
        if not ignored_dirs:
            continue

        print(f"\n开始清理 [{name}] 目录...")
        print(f"  忽略子目录: {', '.join(ignored_dirs)}")
        if keep_patterns:
            print(f"  例外保留: {', '.join(keep_patterns)}")

        for d in ignored_dirs:
            d_clean = d.replace("/**", "").strip("/")
            target_path = root_dir / d_clean
            if not target_path.exists():
                continue
            if not target_path.is_dir():
                continue
            f, dr, k, fl = clean_ignored_dir(
                target_path, root_dir, PROJECT_ROOT, keep_patterns, dry_run=args.dry_run
            )
            total_files += f
            total_dirs += dr
            total_kept += k
            total_failed += fl

    print("\n" + "=" * 60)
    if args.dry_run:
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


if __name__ == "__main__":
    main()
