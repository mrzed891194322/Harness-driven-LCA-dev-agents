import os
import sys
from pathlib import Path
import fnmatch


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
