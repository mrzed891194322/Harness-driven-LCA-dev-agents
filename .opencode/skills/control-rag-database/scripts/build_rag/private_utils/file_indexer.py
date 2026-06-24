from pathlib import Path
from markitdown import MarkItDown
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

def process_file(file_path: Path, md: MarkItDown, collection: chromadb.Collection, text_splitter: RecursiveCharacterTextSplitter):
    """
    转换单个文件内容，切分文本块，并将其添加至 Chroma 向量集合中。
    
    参数:
        file_path (Path): 文件路径。
        md (MarkItDown): MarkItDown 转换实例。
        collection (chromadb.Collection): ChromaDB 向量集合对象。
        text_splitter (RecursiveCharacterTextSplitter): 文本分割器实例。
    """
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
        
        documents = []
        metadatas = []
        ids = []
        
        for i, chunk in enumerate(chunks):
            chunk_stripped = chunk.strip()
            if not chunk_stripped:
                continue
            documents.append(chunk_stripped)
            # 记录数据源信息作为元数据
            metadatas.append({"source": str(file_path)})
            # 为每个文本块生成唯一 ID
            ids.append(f"{file_path.name}_chunk_{i}")
            
        # 如果切分出了有效的文本块，将其批量写入向量数据库中
        if documents:
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Added {len(documents)} chunks from {file_path}")
            
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
