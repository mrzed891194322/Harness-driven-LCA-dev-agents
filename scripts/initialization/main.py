"""
项目初始化脚本

功能：
    1. 检查 opencode CLI 与 RAG embedding API 是否可用
    2. 构建 RAG 知识库（依据映射规则将原始文档向量化写入 Chroma 数据库）
    3. 检查 openLCA IPC Server 是否已启动并可连接，并在连接成功后清理项目对应的 openLCA 实体

参考来源：
    - scripts/initialization/rag_init
    - scripts/initialization/openlca_check

使用方式：
    # 手动模式（默认）：先清理目录并同步文件，再执行环境检查、RAG 构建与 openLCA 检查
    uv run python scripts/initialization/main.py

    # GUI 模式：只执行环境检查、RAG 构建与 openLCA 检查
    uv run python scripts/initialization/main.py --mode gui

    # 仅检查环境
    uv run python scripts/initialization/main.py --only env

    # 仅构建 RAG 知识库
    uv run python scripts/initialization/main.py --only rag

    # 仅检查 openLCA 连接
    uv run python scripts/initialization/main.py --only openlca

    # 自定义 openLCA IPC 端口
    uv run python scripts/initialization/main.py --only openlca --port 8080
"""

import sys
import argparse
import subprocess
from pathlib import Path

# 将本脚本所在目录加入 sys.path 以便导入同目录模块
SCRIPT_DIR = Path(__file__).parent
sys.path.append(str(SCRIPT_DIR))

# 项目根目录：scripts/initialization -> 上溯 2 层
PROJECT_ROOT = SCRIPT_DIR.parents[1]

from rag_init.main import build_all_rag
from rag_init.mapping_rules import DEFAULT_MAPPING
from env_check import check_project_environment
from openlca_check.main import check_openlca
from utils.encoding import setup_io_encoding


def main():
    setup_io_encoding()

    parser = argparse.ArgumentParser(
        description="项目初始化：检查环境 + 构建 RAG 知识库 + 检查 openLCA IPC 连接"
    )
    parser.add_argument(
        "--only",
        choices=["clean", "env", "rag", "openlca"],
        default=None,
        help="仅执行指定任务（clean、env、rag 或 openlca）；省略则依次执行全部任务",
    )
    parser.add_argument(
        "--mode",
        choices=["gui", "manual"],
        default="manual",
        help="初始化模式：gui 仅执行初始化检查与构建；manual 会先执行目录清理和文件同步（默认 manual）",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="openLCA IPC Server 主机地址（默认 localhost）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="openLCA IPC Server 端口（默认 8080）",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="构建 RAG 前先清空各输出子目录中除 README.md 外的内容",
    )
    parser.add_argument(
        "--mapping",
        type=str,
        default=None,
        help=(
            "自定义映射 JSON 文件路径，格式为列表 [{input, output}, ...]；"
            "省略则使用内置默认映射"
        ),
    )
    args = parser.parse_args()

    run_env = args.only in (None, "env")
    run_rag = args.only in (None, "rag")
    run_openlca = args.only in (None, "openlca")

    if args.only == "clean":
        print("=" * 60)
        print("Clean Directories")
        print("=" * 60)
        command = ["uv", "run", "python", "scripts/clean_dir/main.py", "-y"]
        print("Running:", " ".join(command))
        result = subprocess.run(command, cwd=str(PROJECT_ROOT), check=False)
        if result.returncode != 0:
            raise RuntimeError(f"Clean Directories failed with exit code {result.returncode}")
        print("=" * 60)
        print("Initialization process finished")
        print("=" * 60)
        return

    if args.mode == "manual" and args.only is None:
        print("=" * 60)
        print("Pre-step 1/2: Clean Directories")
        print("=" * 60)
        command = ["uv", "run", "python", "scripts/clean_dir/main.py", "-y"]
        print("Running:", " ".join(command))
        result = subprocess.run(command, cwd=str(PROJECT_ROOT), check=False)
        if result.returncode != 0:
            raise RuntimeError(f"Pre-step 1/2: Clean Directories failed with exit code {result.returncode}")

        print("=" * 60)
        print("Pre-step 2/2: Sync Files")
        print("=" * 60)
        command = ["uv", "run", "python", "scripts/file_sync/main.py"]
        print("Running:", " ".join(command))
        result = subprocess.run(command, cwd=str(PROJECT_ROOT), check=False)
        if result.returncode != 0:
            raise RuntimeError(f"Pre-step 2/2: Sync Files failed with exit code {result.returncode}")

    if run_env:
        print("=" * 60)
        print("Step 1/3: Check Environment")
        print("=" * 60)
        check_project_environment(project_root=PROJECT_ROOT)

    if run_rag:
        print("=" * 60)
        print("Step 2/3: Build RAG Knowledge Base")
        print("=" * 60)
        mapping = DEFAULT_MAPPING
        if args.mapping:
            import json
            mapping_path = Path(args.mapping)
            if not mapping_path.is_absolute():
                mapping_path = PROJECT_ROOT / mapping_path
            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
        build_all_rag(PROJECT_ROOT, mapping, clean=args.clean)

    if run_openlca:
        print("=" * 60)
        print("Step 3/3: Check openLCA IPC Server Connection")
        print("=" * 60)
        if check_openlca(host=args.host, port=args.port):
            print("openLCA connection is available; cleaning project entities...")
            cleanup_command = [
                sys.executable,
                "scripts/openlca_cleanup/main.py",
                "--project",
                PROJECT_ROOT.name,
                "--host",
                args.host,
                "--port",
                str(args.port),
                "--yes",
            ]
            print("Running:", " ".join(cleanup_command))
            result = subprocess.run(cleanup_command, cwd=str(PROJECT_ROOT), check=False)
            if result.returncode != 0:
                raise RuntimeError(
                    f"openLCA cleanup failed with exit code {result.returncode}"
                )

    print("=" * 60)
    print("Initialization process finished")
    print("=" * 60)


if __name__ == "__main__":
    main()
