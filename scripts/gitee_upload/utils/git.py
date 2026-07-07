# -*- coding: utf-8 -*-

import subprocess
import sys
from pathlib import Path

def run_git_command(args: list, cwd: Path, dry_run: bool = False):
    """
    运行 git 命令。
    返回 (success, output_string)
    """
    cmd = ["git"] + args
    cmd_str = " ".join(cmd)
    
    if dry_run:
        print(f"  [演练模式] 将运行命令: {cmd_str}")
        return True, "Dry run"
        
    print(f"  运行命令: {cmd_str}")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if result.returncode == 0:
            # 合并输出以获取更多反馈信息（有些 git 输出在 stderr 中，比如 push 进度）
            output = (result.stdout + "\n" + result.stderr).strip()
            return True, output
        else:
            output = (result.stdout + "\n" + result.stderr).strip()
            return False, output
    except Exception as e:
        return False, str(e)


def check_and_setup_gitee_remote(project_root: Path, remote_name: str, default_url: str, dry_run: bool = False) -> bool:
    """
    检查远程源是否存在，如果不存在则自动添加；若 URL 不一致则更新。
    """
    print(f"检查远程源 [{remote_name}]...")
    success, output = run_git_command(["remote"], project_root)
    if not success:
        print(f"获取远程源列表失败: {output}", file=sys.stderr)
        return False

    remotes = [r.strip() for r in output.splitlines() if r.strip()]
    if remote_name not in remotes:
        print(f"未找到远程源 [{remote_name}]，正在添加...")
        if dry_run:
            print(f"  [演练模式] 将添加远程源 [{remote_name}] -> {default_url}")
            return True
        add_success, add_output = run_git_command(["remote", "add", remote_name, default_url], project_root)
        if not add_success:
            print(f"添加远程源失败: {add_output}", file=sys.stderr)
            return False
        print(f"成功添加远程源 [{remote_name}] -> {default_url}")
        return True
    
    # 检查已有的 URL
    url_success, url_output = run_git_command(["remote", "get-url", remote_name], project_root)
    if not url_success:
        print(f"获取远程源 [{remote_name}] 的 URL 失败: {url_output}", file=sys.stderr)
        return False
    
    current_url = url_output.strip()
    if current_url != default_url:
        print(f"远程源 [{remote_name}] 的 URL 不一致:")
        print(f"  当前 URL: {current_url}")
        print(f"  配置 URL: {default_url}")
        print("正在更新远程源 URL...")
        if dry_run:
            print(f"  [演练模式] 将更新远程源 [{remote_name}] URL 为 {default_url}")
            return True
        set_success, set_output = run_git_command(["remote", "set-url", remote_name, default_url], project_root)
        if not set_success:
            print(f"更新远程源 URL 失败: {set_output}", file=sys.stderr)
            return False
        print("远程源 URL 更新成功。")
    else:
        print(f"远程源 [{remote_name}] 已正确配置: {current_url}")
        
    return True


def get_current_branch(project_root: Path) -> str:
    """
    获取当前分支名。
    """
    success, output = run_git_command(["branch", "--show-current"], project_root)
    if success and output:
        # 只取第一行非空内容
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if lines:
            return lines[0]
    
    # 备用方案
    success, output = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], project_root)
    if success and output:
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if lines:
            return lines[0]
    return "master"


def sync_to_gitee(
    project_root: Path,
    remote_name: str,
    branch: str = None,
    all_branches: bool = False,
    tags: bool = False,
    force: bool = False,
    dry_run: bool = False
) -> bool:
    """
    推送代码到远端 Gitee 仓库。
    """
    success_count = 0
    total_commands = 0
    
    # 基本的 push 参数
    push_args = ["push", remote_name]
    if force:
        push_args.append("--force")
        
    # 1. 同步分支
    if all_branches:
        print(f"准备同步所有分支到 [{remote_name}]...")
        cmd_args = push_args + ["--all"]
        total_commands += 1
        success, output = run_git_command(cmd_args, project_root, dry_run)
        if success:
            print(f"所有分支同步成功。\n{output if not dry_run else ''}")
            success_count += 1
        else:
            print(f"所有分支同步失败:\n{output}", file=sys.stderr)
    elif branch:
        print(f"准备同步分支 [{branch}] 到 [{remote_name}]...")
        cmd_args = push_args + [branch]
        total_commands += 1
        success, output = run_git_command(cmd_args, project_root, dry_run)
        if success:
            print(f"分支 [{branch}] 同步成功。\n{output if not dry_run else ''}")
            success_count += 1
        else:
            print(f"分支 [{branch}] 同步失败:\n{output}", file=sys.stderr)
            
    # 2. 同步标签
    if tags:
        print(f"准备同步所有标签到 [{remote_name}]...")
        cmd_args = push_args + ["--tags"]
        total_commands += 1
        success, output = run_git_command(cmd_args, project_root, dry_run)
        if success:
            print(f"所有标签同步成功。\n{output if not dry_run else ''}")
            success_count += 1
        else:
            print(f"所有标签同步失败:\n{output}", file=sys.stderr)
            
    return success_count == total_commands and total_commands > 0
