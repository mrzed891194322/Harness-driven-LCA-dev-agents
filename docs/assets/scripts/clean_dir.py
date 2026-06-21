#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
from pathlib import Path

# 安全保护：在清理过程中绝对不删除/进入的目录名称
IGNORED_DIRS = {
    '.git', 
    '.github', 
    '.vscode', 
    '.idea', 
    'node_modules', 
    '.opencode', 
    '.gemini', 
    '__pycache__', 
    '.venv', 
    'venv', 
    'env'
}

def is_readme(filename: str) -> bool:
    """
    判断文件名是否为 README。
    匹配规则：文件名（不区分大小写）为 'readme'，或者以 'readme.' 开头（例如 readme.md, readme.txt）。
    """
    name = filename.lower()
    return name == "readme" or name.startswith("readme.")

def clean_directory(target_path: Path, dry_run: bool = False) -> tuple:
    """
    遍历并清理目录，删除除了 README 以外的所有文件。
    如果子目录在清理后变为空，则将其一并删除。
    """
    deleted_files = 0
    deleted_dirs = 0
    kept_readmes = 0
    failed_files = 0
    failed_dirs = 0
    
    # 用于在演练模式下记录模拟删除的路径
    simulated_deleted = set()
    
    # topdown=False (自底向上遍历) 使得我们可以先清空子目录中的文件，
    # 接着如果子目录变空了，就可以在同一次遍历中将其删除。
    for root, dirs, files in os.walk(target_path, topdown=False):
        root_path = Path(root)
        
        # 安全检查：如果当前路径中的任何一部分处于被忽略的目录列表中，则跳过
        if any(part in IGNORED_DIRS for part in root_path.parts):
            continue
            
        # 1. 清理当前目录下的文件
        for file in files:
            file_path = root_path / file
            if is_readme(file):
                kept_readmes += 1
                continue
                
            if dry_run:
                print(f"[待删除] 文件: {file_path.relative_to(target_path)}")
                simulated_deleted.add(file_path)
                deleted_files += 1
            else:
                try:
                    file_path.unlink()
                    deleted_files += 1
                    print(f"已删除文件: {file_path.relative_to(target_path)}")
                except Exception as e:
                    failed_files += 1
                    print(f"删除文件失败: {file_path}，错误: {e}", file=sys.stderr)
                    
        # 2. 清理因文件删除而变为空的子目录（不删除传入的 target_path 本身）
        if root_path != target_path:
            try:
                # 检查目录是否变空
                if dry_run:
                    # 演练模式下，如果该目录下的所有子项都在 simulated_deleted 中，则该目录变空
                    is_empty = all(child in simulated_deleted for child in root_path.iterdir())
                else:
                    is_empty = not any(root_path.iterdir())
            except Exception:
                is_empty = False
                
            if is_empty:
                if dry_run:
                    print(f"[待删除] 空目录: {root_path.relative_to(target_path)}")
                    simulated_deleted.add(root_path)
                    deleted_dirs += 1
                else:
                    try:
                        root_path.rmdir()
                        deleted_dirs += 1
                        print(f"已删除空目录: {root_path.relative_to(target_path)}")
                    except Exception as e:
                        failed_dirs += 1
                        print(f"删除目录失败: {root_path}，错误: {e}", file=sys.stderr)
                        
    return deleted_files, deleted_dirs, kept_readmes, failed_files, failed_dirs

def main():
    parser = argparse.ArgumentParser(
        description="遍历指定目录（包含其所有子目录），清除除了 README 以外的所有文件，并自动清理清理后产生的空子目录。"
    )
    parser.add_argument("dir_path", type=str, help="需要清理的目录相对路径（相对于当前工作目录或项目根目录）")
    parser.add_argument("-y", "--yes", action="store_true", help="跳过二次确认，直接执行删除操作")
    parser.add_argument("--dry-run", action="store_true", help="演练模式，仅打印将要删除的文件/目录，不执行实际删除")
    
    args = parser.parse_args()
    
    # 确定项目根目录（脚本在 docs/assets/scripts/clean_dir.py，向上三级为项目根目录）
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent
    
    # 路径解析
    input_path = Path(args.dir_path)
    
    # 1. 尝试相对于当前工作目录解析
    target_path = input_path.expanduser().resolve()
    
    # 2. 如果工作目录下的路径不存在，尝试相对于项目根目录解析
    if not target_path.exists():
        alt_path = (project_root / input_path).resolve()
        if alt_path.exists():
            target_path = alt_path
            
    # 检查路径是否存在且是一个目录
    if not target_path.exists():
        print(f"错误: 路径 '{args.dir_path}' 不存在！", file=sys.stderr)
        sys.exit(1)
    if not target_path.is_dir():
        print(f"错误: 路径 '{args.dir_path}' 不是一个目录！", file=sys.stderr)
        sys.exit(1)
        
    # 安全保护：不允许清理项目根目录本身
    if target_path == project_root:
        print("危险: 不允许直接清理项目根目录！这会导致项目代码和配置被清空。", file=sys.stderr)
        sys.exit(1)
        
    # 安全保护：确保目标目录在项目根目录之内，防止误删外部目录
    is_inside_project = False
    try:
        target_path.relative_to(project_root)
        is_inside_project = True
    except ValueError:
        pass
        
    if not is_inside_project:
        print(f"错误: 安全限制！目标目录 '{target_path}' 不在项目根目录 '{project_root}' 中！", file=sys.stderr)
        sys.exit(1)
        
    print("=" * 60)
    print(f"项目根目录: {project_root}")
    print(f"目标清理目录: {target_path}")
    if args.dry_run:
        print("模式: [演练模式] (只显示，不实际删除文件)")
    print("=" * 60)
    
    # 二次确认
    if not args.yes and not args.dry_run:
        confirm = input(f"警告：这将彻底删除该目录下除了 README 以外的所有文件！\n确定要继续清理目录 '{target_path.relative_to(project_root)}' 吗？(y/N): ")
        if confirm.strip().lower() not in ('y', 'yes'):
            print("操作已取消。")
            sys.exit(0)
            
    # 执行清理
    deleted_files, deleted_dirs, kept_readmes, failed_files, failed_dirs = clean_directory(target_path, dry_run=args.dry_run)
    
    # 打印统计结果
    print("=" * 60)
    if args.dry_run:
        print("演练结果统计：")
        print(f"- 预计删除文件数: {deleted_files}")
        print(f"- 预计删除空目录数: {deleted_dirs}")
        print(f"- 预计保留 README 文件数: {kept_readmes}")
    else:
        print("清理完成！统计结果如下：")
        print(f"- 成功删除文件数: {deleted_files}")
        print(f"- 成功删除空目录数: {deleted_dirs}")
        print(f"- 保留 README 文件数: {kept_readmes}")
        if failed_files > 0 or failed_dirs > 0:
            print(f"- 删除失败文件数: {failed_files}")
            print(f"- 删除失败目录数: {failed_dirs}")
    print("=" * 60)

if __name__ == "__main__":
    main()
