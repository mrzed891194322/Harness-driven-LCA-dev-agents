"""
RAG 知识库构建模块

依据映射规则（参考 control-rag-database/instruction/mapping-rules.md），
将原始文档目录中的文件向量化写入对应的 Chroma 数据库子目录。

默认映射（路径相对于项目根目录）：
    - src/input/knowledge_base/standards    -> src/knowledge/standards
    - src/input/knowledge_base/openlca_manual -> src/knowledge/openlca_manual
    - src/input/user_file                   -> src/knowledge/input
"""

import sys
import shutil
from pathlib import Path

# 将本脚本所在目录加入 sys.path 以便导入同目录下的 utils 包
sys.path.append(str(Path(__file__).parent))

from markitdown import MarkItDown
from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils.embedding import load_embedding_config
from utils.file_filter import get_supported_extensions, is_supported_file
from utils.db import init_chroma_collection
from utils.file_indexer import process_file
from mapping_rules import DEFAULT_MAPPING

# 配置文件（支持的后缀类型）位于本模块同目录
CONFIG_PATH = Path(__file__).parent / "config.json"


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


def _build_single(project_root: Path, input_dir: Path, output_dir: Path):
    """对单个 input->output 映射执行 RAG 构建。"""
    try:
        input_display = input_dir.relative_to(project_root)
        output_display = output_dir.relative_to(project_root)
    except ValueError:
        input_display = input_dir
        output_display = output_dir

    print(f"\n--- Building: {input_display}  ->  {output_display} ---")

    # 加载 embedding 配置
    try:
        api_key, api_url, model_name = load_embedding_config()
    except ValueError as e:
        print(f"Error: {e}")
        return

    supported_extensions = get_supported_extensions(CONFIG_PATH)
    print(f"Supported document extensions: {supported_extensions}")

    if not input_dir.exists():
        print(f"Input directory does not exist, skipping: {input_display}")
        return

    input_dir.mkdir(parents=True, exist_ok=True)

    # 扫描并过滤合法文件
    files = list(input_dir.rglob("*"))
    valid_files = [
        f for f in files if f.is_file() and is_supported_file(f, supported_extensions)
    ]

    if valid_files:
        print("Initializing MarkItDown for disk conversion...")
        md = MarkItDown()
        for file_path in valid_files:
            if file_path.suffix.lower() == ".md":
                continue
            try:
                try:
                    display_path = file_path.relative_to(project_root)
                except ValueError:
                    display_path = file_path
                print(f"Converting {display_path} to markdown on disk...")
                result = md.convert(str(file_path))
                md_content = result.text_content
                output_md_path = file_path.with_suffix(".md")
                try:
                    display_out_path = output_md_path.relative_to(project_root)
                except ValueError:
                    display_out_path = output_md_path
                with open(output_md_path, "w", encoding="utf-8") as out_f:
                    out_f.write(md_content)
                print(f"Saved -> {display_out_path}")
            except Exception as e:
                print(f"Error converting {display_path}: {e}")
    else:
        print(f"No convertible files in {input_display}.")

    # 仅读取 .md 文件写入向量库
    md_files = [
        f for f in input_dir.rglob("*")
        if f.is_file() and f.suffix.lower() == ".md" and not f.name.startswith(".")
    ]
    if not md_files:
        print(f"No .md files in {input_display}, skip database creation.")
        return

    print(f"Found {len(md_files)} .md files. Initializing ChromaDB...")
    collection = init_chroma_collection(output_dir, api_key, api_url, model_name)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200
    )
    md_instance = MarkItDown()
    for file_path in md_files:
        process_file(file_path, md_instance, collection, text_splitter, project_root)

    print(f"RAG build completed for {output_display}")


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
        input_rel = item.get("input")
        output_rel = item.get("output")
        if not input_rel or not output_rel:
            print(f"Skipping invalid mapping item: {item}")
            continue

        input_dir = project_root / input_rel
        output_dir = project_root / output_rel

        if clean:
            print(f"Cleaning output directory (preserving README.md): {output_rel}")
            _clean_output_dir(output_dir)

        _build_single(project_root, input_dir, output_dir)

    print("\nAll RAG mappings built successfully.")