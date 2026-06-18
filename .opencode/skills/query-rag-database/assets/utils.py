import os
from pathlib import Path
from dotenv import load_dotenv
import chromadb
import chromadb.utils.embedding_functions as embedding_functions

def load_embedding_config():
    """
    加载并验证从环境变量配置的嵌入（embedding）相关 API 参数。
    
    返回:
        tuple: (api_key, api_url, model_name) 分别对应 API 密钥、自定义接口地址和模型名称。
    """
    load_dotenv()
    api_key = os.getenv("EMBEDDING_API_KEY")
    api_url = os.getenv("EMBEDDING_API_URL")
    model_name = os.getenv("EMBEDDING_MODEL")
    
    # 验证 API 密钥是否已配置且非占位符
    if not api_key or api_key == "sk-your-api-key-here":
        raise ValueError("Please set a valid EMBEDDING_API_KEY in .env")
        
    return api_key, api_url, model_name

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
