#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

def run_git_cmd(args, cwd):
    """运行git命令并捕获/打印输出"""
    print(f"Running: git {' '.join(args)}")
    result = subprocess.run(['git'] + args, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error executing 'git {' '.join(args)}':", file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return False, result.stdout, result.stderr
    return True, result.stdout, result.stderr

def main():
    # 确定 wiki 目录路径 (脚本已转移到 docs/wiki/assets/scripts，wiki 目录即为其上两层目录)
    script_dir = Path(__file__).resolve().parent
    wiki_dir = (script_dir / "../..").resolve()

    if not wiki_dir.exists():
        print(f"Error: Wiki directory not found at {wiki_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Wiki directory: {wiki_dir}")

    # 1. 检查 git 状态
    success, stdout, stderr = run_git_cmd(['status', '--porcelain'], cwd=wiki_dir)
    if not success:
        sys.exit(1)

    if not stdout.strip():
        print("No changes to commit. Everything is up-to-date.")
        sys.exit(0)

    print("Detected changes in Wiki:")
    print(stdout)

    # 2. 准备 commit message
    # 默认提交信息，使用当前时间
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    default_msg = f"Update wiki docs ({now_str})"
    
    # 如果通过命令行参数传入了自定义 commit message
    if len(sys.argv) > 1:
        commit_msg = " ".join(sys.argv[1:])
    else:
        commit_msg = default_msg

    print(f"Commit message: {commit_msg}")

    # 3. 执行 git add
    success, _, _ = run_git_cmd(['add', '-A'], cwd=wiki_dir)
    if not success:
        sys.exit(1)

    # 4. 执行 git commit
    success, stdout, _ = run_git_cmd(['commit', '-m', commit_msg], cwd=wiki_dir)
    if not success:
        sys.exit(1)
    print(stdout)

    # 5. 执行 git push
    # 同时推送至 origin 和 github
    remotes = ['origin', 'github']
    failed_remotes = []
    
    for remote in remotes:
        print(f"\n[Push] Pushing to remote: {remote}...")
        success, stdout, stderr = run_git_cmd(['push', remote, 'master'], cwd=wiki_dir)
        if not success:
            failed_remotes.append(remote)
        else:
            if stdout:
                print(stdout)
            if stderr:
                print(stderr)

    if failed_remotes:
        print(f"\nError: Failed to push to the following remotes: {', '.join(failed_remotes)}", file=sys.stderr)
        sys.exit(1)

    print("\nSuccess: Wiki updated and pushed to all remotes successfully!")

if __name__ == "__main__":
    main()
