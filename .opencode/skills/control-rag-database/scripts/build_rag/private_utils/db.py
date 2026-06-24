from pathlib import Path
import chromadb
import chromadb.utils.embedding_functions as embedding_functions

def init_chroma_collection(output_dir: Path, api_key: str, api_url: str, model_name: str) -> chromadb.Collection:
    """
    初始化 Chroma 客户端并创建/重建向量数据库集合。
    
    参数:
        output_dir (Path): 数据库持久化存储的目录。
        api_key (str): OpenAI/Embedding API 的密钥。
        api_url (str): 可选，自定义的 API 基础地址（api_base）。
        model_name (str): 嵌入模型名称。
        
    返回:
        chromadb.Collection: 创建成功的 ChromaDB 集合对象。
    """
    # 确保输出目录及其父级目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Initializing ChromaDB at {output_dir}...")
    client = chromadb.PersistentClient(path=str(output_dir))
    
    # 配置 OpenAI 嵌入函数需要的参数
    kwargs = {"api_key": api_key, "model_name": model_name}
    if api_url:
        kwargs["api_base"] = api_url
        
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(**kwargs)
    
    # 为了保证数据完全重建，先尝试删除已有的同名 collection
    try:
        client.delete_collection(name="rag_collection")
        print("Existing collection deleted for a clean rebuild.")
    except Exception:
        pass
        
    # 创建新的 collection
    collection = client.create_collection(
        name="rag_collection", 
        embedding_function=openai_ef
    )
    return collection
