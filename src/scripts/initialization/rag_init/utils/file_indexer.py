from pathlib import Path
from markitdown import MarkItDown
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter


def process_file(file_path: Path, md: MarkItDown, collection: chromadb.Collection, text_splitter: RecursiveCharacterTextSplitter):
    """
    转换单个文件内容，切分文本块，并将其添加至 Chroma 向量集合中。
    """
    print(f"Processing {file_path}...")
    try:
        if file_path.suffix.lower() in (".md", ".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                text_content = f.read()
        else:
            result = md.convert(str(file_path))
            text_content = result.text_content

        chunks = text_splitter.split_text(text_content)

        documents = []
        metadatas = []
        ids = []

        for i, chunk in enumerate(chunks):
            chunk_stripped = chunk.strip()
            if not chunk_stripped:
                continue
            documents.append(chunk_stripped)
            metadatas.append({"source": str(file_path)})
            ids.append(f"{file_path.name}_chunk_{i}")

        if documents:
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            print(f"Added {len(documents)} chunks from {file_path}")

    except Exception as e:
        print(f"Error processing {file_path}: {e}")