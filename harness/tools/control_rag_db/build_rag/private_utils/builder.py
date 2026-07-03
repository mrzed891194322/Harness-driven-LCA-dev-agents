import time
from pathlib import Path
import chromadb
from markitdown import MarkItDown
from langchain_text_splitters import RecursiveCharacterTextSplitter

from utils.embedding import load_embedding_config
from private_utils.db import init_chroma_collection
from private_utils.file_filter import get_supported_extensions, is_supported_file
from private_utils.file_indexer import process_file

def add_batch_with_adaptive_retry(
    collection: chromadb.Collection,
    documents: list[str],
    metadatas: list[dict],
    ids: list[str],
    max_retries: int = 5,
    initial_delay: float = 1.0
):
    """
    尝试向 Chroma 集合中添加一批文本块。
    如果遇到服务器端限制（如 429 频控、请求体过大、Token 超出限制等），
    采用指数退避重试或自动拆分小批量的策略，保证数据可靠写入。
    """
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            return  # 写入成功，直接返回
        except Exception as e:
            err_msg = str(e).lower()
            
            # 判断是否是大小或 Token 限制造成的失败
            is_size_limit = any(x in err_msg for x in (
                "too large", "maximum request size", "context length", 
                "token limit", "413", "length limit", "too many tokens"
            ))
            
            # 如果是大小限制，且当前批次大于 1，直接拆分
            if is_size_limit and len(documents) > 1:
                mid = len(documents) // 2
                print(f"[Warning] Batch size/token limit exceeded ({len(documents)} items). Splitting into smaller batches (sizes: {mid}, {len(documents) - mid})...")
                add_batch_with_adaptive_retry(collection, documents[:mid], metadatas[:mid], ids[:mid], max_retries, initial_delay)
                add_batch_with_adaptive_retry(collection, documents[mid:], metadatas[mid:], ids[mid:], max_retries, initial_delay)
                return
                
            # 如果是其它错误（如频控 429、网络超时等），进行退避重试
            is_rate_limit = any(x in err_msg for x in ("429", "rate limit", "too many requests", "rate_limit"))
            if is_rate_limit and attempt < max_retries - 1:
                print(f"[Warning] API rate limit hit. Retrying in {delay:.1f}s (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
                delay *= 2
            elif attempt < max_retries - 1:
                print(f"[Warning] API request failed (Error: {e}). Retrying in {delay:.1f}s (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
                delay *= 2
            else:
                # 重试机会耗尽，如果当前批次依然大于 1，尝试作为最后的兜底手段，将其对半拆分写入
                if len(documents) > 1:
                    mid = len(documents) // 2
                    print(f"[Warning] Max retries reached. Attempting to split batch (sizes: {mid}, {len(documents) - mid})...")
                    add_batch_with_adaptive_retry(collection, documents[:mid], metadatas[:mid], ids[:mid], max_retries, initial_delay)
                    add_batch_with_adaptive_retry(collection, documents[mid:], metadatas[mid:], ids[mid:], max_retries, initial_delay)
                    return
                else:
                    print(f"[Error] Failed to add document batch to Chroma after {max_retries} attempts: {e}")
                    raise e

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
    
    # 循环处理每一份 md 文件，收集所有文本块
    all_documents = []
    all_metadatas = []
    all_ids = []
    
    md_instance = MarkItDown()
    for file_path in md_files:
        chunks_data = process_file(file_path, md_instance, text_splitter)
        for doc, meta, cid in chunks_data:
            all_documents.append(doc)
            all_metadatas.append(meta)
            all_ids.append(cid)
            
    # 分批写入 Chroma 数据库（每批 500 个文本块）
    batch_size = 500
    total_chunks = len(all_documents)
    if total_chunks > 0:
        print(f"Adding {total_chunks} total chunks to Chroma database in batches of {batch_size}...")
        for i in range(0, total_chunks, batch_size):
            batch_docs = all_documents[i:i+batch_size]
            batch_metas = all_metadatas[i:i+batch_size]
            batch_ids = all_ids[i:i+batch_size]
            
            add_batch_with_adaptive_retry(
                collection=collection,
                documents=batch_docs,
                metadatas=batch_metas,
                ids=batch_ids
            )
            print(f"Added batch {i // batch_size + 1}/{(total_chunks + batch_size - 1) // batch_size} ({len(batch_docs)} chunks)")
        
    print("RAG database build completed successfully.")
