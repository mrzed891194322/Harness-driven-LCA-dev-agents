"""
RAG 知识库批量构建入口

按照 mapping_rules.DEFAULT_MAPPING 定义的路径映射，
# 批量调用 harness/tools/control_rag_db 中的 build_rag 工具构建 RAG 知识库。
"""

import sys
import shutil
import argparse
from pathlib import Path

# ── 注入工具路径 ──────────────────────────────────────────────────────────────
# scripts/initialization/rag_init/main.py
#   parents[3] = project root
_BUILD_RAG_DIR = Path(__file__).parents[3] / "harness" / "tools" / "control_rag_db" / "build_rag"
_CTRL_RAG_DIR  = Path(__file__).parents[3] / "harness" / "tools" / "control_rag_db"

# build_rag 内部通过 parent.parent (即 control_rag_db/) 来导入 utils
sys.path.insert(0, str(_BUILD_RAG_DIR))   # 使 private_utils 可被找到
sys.path.insert(0, str(_CTRL_RAG_DIR))    # 使 utils (encoding, embedding) 可被找到

from private_utils.builder import build_rag
from utils.encoding import setup_io_encoding

# ── 导入本模块的映射规则 ──────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from mapping_rules import DEFAULT_MAPPING


def _clean_output_dir(output_dir: Path):
    """清空输出目录中除 README.md 外的所有文件和子目录。"""
    if not output_dir.exists():
        return
    for p in output_dir.iterdir():
        if p.name == "README.md":
            continue
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()


def build_all_rag(project_root: Path, mapping: list, clean: bool = False):
    """
    依据映射列表批量构建 RAG 知识库。

    参数:
        project_root (Path): 项目根目录。
        mapping (list): 形如 [{"input": "...", "output": "..."}] 的映射列表（相对路径）。
        clean (bool): 构建前是否清空输出子目录（保留 README.md）。
    """
    print(f"Project root: {project_root}")
    print(f"Number of mapping entries: {len(mapping)}")

    for item in mapping:
        input_rel  = item.get("input")
        output_rel = item.get("output")
        if not input_rel or not output_rel:
            print(f"Skipping invalid mapping item: {item}")
            continue

        input_dir  = project_root / input_rel
        output_dir = project_root / output_rel

        if clean:
            print(f"Cleaning output directory (preserving README.md): {output_rel}")
            _clean_output_dir(output_dir)

        print(f"\n--- Building: {input_rel}  ->  {output_rel} ---")
        build_rag(input_dir, output_dir)

    print("\nAll RAG mappings built successfully.")


def main():
    setup_io_encoding()

    parser = argparse.ArgumentParser(
        description="按映射规则批量构建 RAG 知识库（调用 harness/tools/control_rag_db/build_rag）"
    )
    parser.add_argument(
        "--project-root",
        type=str,
        default=None,
        help="项目根目录（默认自动推断为本脚本的 parents[3]）"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="构建前清空各输出子目录（保留 README.md）"
    )
    args = parser.parse_args()

    if args.project_root:
        project_root = Path(args.project_root).resolve()
    else:
        # scripts/initialization/rag_init/ -> parents[3] = 项目根
        project_root = Path(__file__).parents[3].resolve()

    build_all_rag(project_root, DEFAULT_MAPPING, clean=args.clean)


if __name__ == "__main__":
    main()