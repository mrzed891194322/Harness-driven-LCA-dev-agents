#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Git 同步至 Gitee 入口脚本

功能：
    将本地 Git 仓库中的分支/标签同步到远端 Gitee 源中。

使用方式：
    # 同步当前分支
    uv run python src/scripts/gitee_upload/main.py
    
    # 同步所有分支和标签
    uv run python src/scripts/gitee_upload/main.py --all --tags
    
    # 强制同步指定分支
    uv run python src/scripts/gitee_upload/main.py --branch master --force
    
    # 演练模式
    uv run python src/scripts/gitee_upload/main.py --dry-run
"""

import sys
import argparse
from pathlib import Path

# 将本脚本所在目录加入 sys.path 以便导入同目录模块
SCRIPT_DIR = Path(__file__).parent
sys.path.append(str(SCRIPT_DIR))

from config import GIT_REMOTE_NAME, DEFAULT_GITEE_URL, PROJECT_ROOT
from utils.git import check_and_setup_gitee_remote, get_current_branch, sync_to_gitee


def main():
    parser = argparse.ArgumentParser(
        description="将本地 Git 仓库的分支/标签同步到远端 Gitee 源中。"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="同步本地所有分支到 Gitee"
    )
    parser.add_argument(
        "--tags",
        action="store_true",
        help="同步本地所有标签到 Gitee"
    )
    parser.add_argument(
        "--branch",
        type=str,
        help="同步指定的分支（如果未指定 --all，默认同步当前分支）"
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="强制推送（对应 git push --force），请谨慎使用"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="演练模式，仅打印将要运行的 Git 命令，不执行实际操作"
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="跳过二次确认（尤其是使用 --force 时的安全提示）"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Git 同步至 Gitee 脚本启动")
    print(f"项目根目录: {PROJECT_ROOT}")
    if args.dry_run:
        print("模式: [演练模式] (只显示，不实际推送)")
    print("=" * 60)

    # 1. 检查和配置远程源
    if not check_and_setup_gitee_remote(PROJECT_ROOT, GIT_REMOTE_NAME, DEFAULT_GITEE_URL, dry_run=args.dry_run):
        print("远程源配置检查未通过，同步终止。", file=sys.stderr)
        sys.exit(1)
        
    # 2. 确定同步内容
    sync_all = args.all
    sync_tags = args.tags
    sync_branch = args.branch
    
    if not sync_all and not sync_branch:
        # 默认同步当前分支
        sync_branch = get_current_branch(PROJECT_ROOT)
        print(f"未指定同步内容，默认选择当前分支: {sync_branch}")
        
    # 3. 强制推送的安全确认
    if args.force and not args.yes and not args.dry_run:
        print("\n" + "!" * 60)
        print("警告：您启用了强制推送 (--force)！这可能会覆盖远程仓库的提交记录，导致数据丢失！")
        print("!" * 60)
        confirm = input("确定要强制推送吗？(y/N): ")
        if confirm.strip().lower() not in ("y", "yes"):
            print("操作已取消。")
            sys.exit(0)

    # 4. 执行同步
    print("\n开始执行同步...")
    success = sync_to_gitee(
        project_root=PROJECT_ROOT,
        remote_name=GIT_REMOTE_NAME,
        branch=sync_branch,
        all_branches=sync_all,
        tags=sync_tags,
        force=args.force,
        dry_run=args.dry_run
    )
    
    print("\n" + "=" * 60)
    if success:
        print("同步完成！")
    else:
        print("同步失败！请检查上述日志。", file=sys.stderr)
    print("=" * 60)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
