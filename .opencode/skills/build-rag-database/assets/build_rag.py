import argparse
from pathlib import Path
from markitdown import MarkItDown
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils import (
    load_embedding_config,
    get_supported_extensions,
    is_supported_file,
    init_chroma_collection,
    process_file
)

def build_rag(input_dir: Path, output_dir: Path):
    """
    从指定的输入目录中读取支持的文档，提取并嵌入后构建 RAG Chroma 向量数据库存入指定输出目录。
    
    参数:
        input_dir (Path): 存放原始文档的输入目录。
        output_dir (Path): 存放向量数据库的输出目录。
    """
    # 加载 embedding 相关的环境变量配置
    try:
        api_key, api_url, model_name = load_embedding_config()
    except ValueError as e:
        print(f"Error: {e}")
        return

    # 确定配置文件的路径并读取支持的后缀类型
    config_path = Path(__file__).parent / "config.json"
    supported_extensions = get_supported_extensions(config_path)
    print(f"Supported document extensions loaded from config: {supported_extensions}")

    # 确保输入目录存在
    input_dir.mkdir(parents=True, exist_ok=True)
    
    # 扫描输入目录，并按照支持的后缀过滤合法文件
    files = list(input_dir.rglob("*"))
    valid_files = [f for f in files if f.is_file() and is_supported_file(f, supported_extensions)]
    
    if not valid_files:
        print(f"No valid files matching {supported_extensions} found in {input_dir}")
        return
        
    print(f"Initializing MarkItDown...")
    md = MarkItDown()
    
    # 初始化 ChromaDB 集合
    collection = init_chroma_collection(output_dir, api_key, api_url, model_name)
    
    # 设置 LangChain 文本切分器：单块大小为 1000 字符，重叠 200 字符
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    
    # 循环处理每一份有效的文件
    for file_path in valid_files:
        process_file(file_path, md, collection, text_splitter)
        
    print("RAG database build completed successfully.")

def main():
    parser = argparse.ArgumentParser(description="Build RAG database from input files.")
    parser.add_argument(
        "--input-dir", "-i",
        type=str,
        default="input",
        help="Input directory containing PDF/Word/Markdown/Text files (default: input)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="src/knowledge",
        help="Output directory for Chroma RAG database (default: src/knowledge)"
    )
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    build_rag(input_dir, output_dir)

if __name__ == "__main__":
    main()
