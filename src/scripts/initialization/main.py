"""
项目初始化脚本

功能：
    1. 构建 RAG 知识库（依据映射规则将原始文档向量化写入 Chroma 数据库）
    2. 检查 openLCA IPC Server 是否已启动并可连接

参考来源：
    - .opencode/skills/external-tools/assets/control-rag-database/scripts/build_rag
    - .opencode/skills/external-tools/assets/control-openlca/scripts/utils/connection.py

使用方式：
    # 同时执行 RAG 构建与 openLCA 检查（默认）
    uv run python src/scripts/initialization/main.py

    # 仅构建 RAG 知识库
    uv run python src/scripts/initialization/main.py --only rag

    # 仅检查 openLCA 连接
    uv run python src/scripts/initialization/main.py --only openlca

    # 自定义 openLCA IPC 端口
    uv run python src/scripts/initialization/main.py --only openlca --port 8080
"""

import sys
import argparse
from pathlib import Path

# 将本脚本所在目录加入 sys.path 以便导入同目录模块
SCRIPT_DIR = Path(__file__).parent
sys.path.append(str(SCRIPT_DIR))

# 项目根目录：src/scripts/initialization -> 上溯 3 层
PROJECT_ROOT = SCRIPT_DIR.parents[2]

from rag_init.main import build_all_rag
from rag_init.mapping_rules import DEFAULT_MAPPING
from openlca_check.main import check_openlca
from rag_init.utils.encoding import setup_io_encoding


def main():
    setup_io_encoding()

    parser = argparse.ArgumentParser(
        description="项目初始化：构建 RAG 知识库 + 检查 openLCA IPC 连接"
    )
    parser.add_argument(
        "--only",
        choices=["rag", "openlca"],
        default=None,
        help="仅执行指定任务（rag 或 openlca）；省略则依次执行两者",
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

    run_rag = args.only in (None, "rag")
    run_openlca = args.only in (None, "openlca")

    if run_rag:
        print("=" * 60)
        print("Step 1/2: Build RAG Knowledge Base")
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
        print("Step 2/2: Check openLCA IPC Server Connection")
        print("=" * 60)
        check_openlca(host=args.host, port=args.port)

    print("=" * 60)
    print("Initialization process finished")
    print("=" * 60)


if __name__ == "__main__":
    main()