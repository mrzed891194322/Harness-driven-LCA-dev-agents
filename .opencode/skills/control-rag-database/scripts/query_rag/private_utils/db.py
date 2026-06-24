from pathlib import Path
import chromadb
import chromadb.utils.embedding_functions as embedding_functions

def get_chroma_collection(knowledge_dir: Path, api_key: str, api_url: str, model_name: str) -> chromadb.Collection:
    """
    初始化 Chroma 客户端并获取已有的向量数据库集合。
    
    参数:
        knowledge_dir (Path): 向量数据库的本地持久化存放目录。
        api_key (str): OpenAI/Embedding API 的密钥。
        api_url (str): 可选，自定义的 API 基础地址（api_base）。
        model_name (str): 嵌入模型名称。
        
    返回:
        chromadb.Collection: 获取得到的 ChromaDB 集合对象。
    """
    client = chromadb.PersistentClient(path=str(knowledge_dir))
    
    # 配置 OpenAI 嵌入函数
    kwargs = {"api_key": api_key, "model_name": model_name}
    if api_url:
        kwargs["api_base"] = api_url
        
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(**kwargs)
    
    return client.get_collection(name="rag_collection", embedding_function=openai_ef)
