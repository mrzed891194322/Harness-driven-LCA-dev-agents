from pathlib import Path
import chromadb
import chromadb.utils.embedding_functions as embedding_functions


def init_chroma_collection(output_dir: Path, api_key: str, api_url: str, model_name: str) -> chromadb.Collection:
    """
    初始化 Chroma 客户端并创建/重建向量数据库集合。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Initializing ChromaDB at {output_dir}...")
    client = chromadb.PersistentClient(path=str(output_dir))

    kwargs = {"api_key": api_key, "model_name": model_name}
    if api_url:
        kwargs["api_base"] = api_url
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(**kwargs)

    # 先删除已有同名 collection 以保证完全重建
    try:
        client.delete_collection(name="rag_collection")
        print("Existing collection deleted for a clean rebuild.")
    except Exception:
        pass

    collection = client.create_collection(
        name="rag_collection",
        embedding_function=openai_ef
    )
    return collection