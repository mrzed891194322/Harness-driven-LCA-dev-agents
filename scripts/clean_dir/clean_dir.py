#!/usr/bin/env python
# -*- coding: utf-8 -*-

r"""
按照 GUI/.gitignore、workspace/.gitignore 和 harness/knowledge/.gitignore 中声明的忽略规则清理文件。

用法：
    uv run python scripts\clean_dir\clean_dir.py              # 交互确认后执行
    uv run python scripts\clean_dir\clean_dir.py --dry-run    # 演练模式，仅打印不删除
    uv run python scripts\clean_dir\clean_dir.py -y           # 跳过确认直接执行
"""

import os
import sys
import argparse
from pathlib import Path


# 解析 .gitignore，返回 (ignored_dirs, keep_patterns)
def parse_gitignore(gitignore_path: Path):
    """
    解析 .gitignore 文件。
    返回:
        ignored_dirs: list[str]  被忽略的目录相对路径（如 'knowledge/'）
        keep_patterns: list[str]  例外保留的相对路径（如 'knowledge/README.md'）
    """
    ignored_dirs = []
    keep_patterns = []

    if not gitignore_path.exists():
        return ignored_dirs, keep_patterns

    with open(gitignore_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            # 跳过空行和注释
            if not line or line.startswith("#"):
                continue
            # 例外保留项
            if line.startswith("!"):
                keep_patterns.append(line[1:].strip())
                continue
            # 被忽略的目录（以 / 结尾 或 /** 结尾）
            if line.endswith("/") or line.endswith("/**"):
                ignored_dirs.append(line)
                continue
            # 普通忽略项（文件），也加入忽略列表
            ignored_dirs.append(line)

    return ignored_dirs, keep_patterns


def match_keep(path: Path, base: Path, keep_patterns) -> bool:
    """
    判断 path（相对于 base 的相对路径）是否匹配任一例外保留规则。
    支持精确匹配和通配符 * 匹配。
    """
    try:
        rel = path.relative_to(base).as_posix()
    except ValueError:
        return False

    for pat in keep_patterns:
        pat = pat.strip("/")
        # 精确匹配
        if rel == pat:
            return True
        # 通配符匹配
        if "*" in pat:
            import fnmatch
            if fnmatch.fnmatch(rel, pat):
                return True
        # 目录前缀匹配：如 keep 'knowledge/README.md'，path 为 'knowledge/README.md'
        if rel.startswith(pat + "/") or pat.startswith(rel + "/"):
            return True
    return False


def clean_ignored_dir(dir_path: Path, base: Path, project_root: Path, keep_patterns, dry_run: bool = False):
    """
    清理单个被忽略的目录：删除所有文件（保留例外项），并删除变空的子目录。
    不删除 dir_path 本身。
    """
    deleted_files = 0
    deleted_dirs = 0
    kept_files = 0
    failed = 0
    simulated_deleted = set()

    for root, dirs, files in os.walk(dir_path, topdown=False):
        root_path = Path(root)

        # 1. 清理文件
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
            else:
                try:
                    file_path.unlink()
                    deleted_files += 1
                    print(f"  已删除文件: {display_path}")
                except Exception as e:
                    failed += 1
                    print(f"  删除文件失败: {file_path}，错误: {e}", file=sys.stderr)

        # 2. 清理变空的子目录（不删除被忽略目录本身）
        if root_path != dir_path:
            try:
                if dry_run:
                    is_empty = all(child in simulated_deleted for child in root_path.iterdir())
                else:
                    is_empty = not any(root_path.iterdir())
            except Exception:
                is_empty = False

            if is_empty:
                try:
                    display_path = root_path.relative_to(project_root)
                except ValueError:
                    display_path = root_path
                if dry_run:
                    print(f"  [待删除] 空目录: {display_path}")
                    simulated_deleted.add(root_path)
                    deleted_dirs += 1
                else:
                    try:
                        root_path.rmdir()
                        deleted_dirs += 1
                        print(f"  已删除空目录: {display_path}")
                    except Exception as e:
                        failed += 1
                        print(f"  删除目录失败: {root_path}，错误: {e}", file=sys.stderr)

    return deleted_files, deleted_dirs, kept_files, failed


def main():
    parser = argparse.ArgumentParser(
        description="按照 GUI、workspace 和 harness/knowledge 目录下的 .gitignore 规则清理生成及临时文件。"
    )
    parser.add_argument("--dry-run", action="store_true", help="演练模式，仅打印将要删除的文件/目录，不执行实际删除")
    parser.add_argument("-y", "--yes", action="store_true", help="跳过二次确认，直接执行删除操作")
    args = parser.parse_args()

    # 脚本位于 scripts/clean_dir/clean_dir.py
    # 项目根目录 = 脚本向上二级
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parents[1]

    # 清理的目标目录及其对应的配置文件和名称
    targets = [
        ("GUI", project_root / "GUI"),
        ("workspace", project_root / "workspace"),
        ("harness/knowledge", project_root / "harness" / "knowledge"),
    ]

    print("=" * 60)
    print(f"项目根目录: {project_root}")
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

    for name, root_dir in targets:
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
            target = root_dir / d_clean
            if not target.exists():
                continue
            if not target.is_dir():
                continue
            f, dr, k, fl = clean_ignored_dir(target, root_dir, project_root, keep_patterns, dry_run=args.dry_run)
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