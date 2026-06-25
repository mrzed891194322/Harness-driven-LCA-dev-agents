from pathlib import Path
from markitdown import MarkItDown
from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils.embedding import load_embedding_config
from private_utils.db import init_chroma_collection
from private_utils.file_filter import get_supported_extensions, is_supported_file
from private_utils.file_indexer import process_file

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
    
    if valid_files:
        print(f"Initializing MarkItDown for disk conversion...")
        md = MarkItDown()
        
        # 调用 markitdown 将所有支持的文件在原目录下转化为 .md 文件
        for file_path in valid_files:
            if file_path.suffix.lower() == ".md":
                continue
            try:
                print(f"Converting {file_path} to markdown on disk...")
                result = md.convert(str(file_path))
                md_content = result.text_content
                output_md_path = file_path.with_suffix(".md")
                with open(output_md_path, "w", encoding="utf-8") as out_f:
                    out_f.write(md_content)
                print(f"Successfully converted and saved to {output_md_path}")
            except Exception as e:
                print(f"Error converting {file_path} to markdown: {e}")
    else:
        print(f"No original files matching {supported_extensions} found in {input_dir} for conversion.")

    # 接下来只读取所有 md 文件并写入 RAG 知识库
    md_files = [
        f for f in input_dir.rglob("*")
        if f.is_file() and f.suffix.lower() == ".md" and not f.name.startswith('.')
    ]
    
    if not md_files:
        print(f"No .md files found in {input_dir} to write to RAG database.")
        return
        
    print(f"Found {len(md_files)} .md files to index. Initializing database...")
    
    # 初始化 ChromaDB 集合
    collection = init_chroma_collection(output_dir, api_key, api_url, model_name)
    
    # 设置 LangChain 文本切分器：单块大小为 1000 字符，重叠 200 字符
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    
    # 循环处理并写入每一份 md 文件
    md_instance = MarkItDown()
    for file_path in md_files:
        process_file(file_path, md_instance, collection, text_splitter)
        
    print("RAG database build completed successfully.")
