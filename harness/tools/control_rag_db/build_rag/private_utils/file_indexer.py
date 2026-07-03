from pathlib import Path
from markitdown import MarkItDown
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

def process_file(file_path: Path, md: MarkItDown, text_splitter: RecursiveCharacterTextSplitter) -> list[tuple[str, dict, str]]:
    """
    转换单个文件内容，切分文本块，并返回其 (document, metadata, id) 元组的列表。
    
    参数:
        file_path (Path): 文件路径。
        md (MarkItDown): MarkItDown 转换实例。
        text_splitter (RecursiveCharacterTextSplitter): 文本分割器实例。
    """
    chunks_data = []
    print(f"Processing {file_path}...")
    try:
        # 如果是 .md 或 .txt 文件，直接读取内容，避免使用 markitdown 重复转换；其他格式则使用 markitdown 转换
        if file_path.suffix.lower() in (".md", ".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                text_content = f.read()
        else:
            result = md.convert(str(file_path))
            text_content = result.text_content
        
        # 将文本切分为较小的 chunk 以便于向量检索
        chunks = text_splitter.split_text(text_content)
        
        import hashlib
        file_hash = hashlib.md5(str(file_path.resolve()).encode("utf-8")).hexdigest()[:8]
        
        for i, chunk in enumerate(chunks):
            chunk_stripped = chunk.strip()
            if not chunk_stripped:
                continue
            # 记录数据源信息作为元数据，并为每个文本块生成唯一 ID (包含路径 hash 避免同名文件如 README.md 冲突)
            chunks_data.append((
                chunk_stripped,
                {"source": str(file_path)},
                f"{file_path.name}_{file_hash}_chunk_{i}"
            ))
            
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
    return chunks_data
