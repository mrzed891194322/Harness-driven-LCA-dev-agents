from pathlib import Path
from typing import List, Dict, Any

from utils.embedding import load_embedding_config
from utils.db import get_chroma_collection

def retrieve_rag_chunks(knowledge_dir: Path, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
    """
    在指定的 Chroma 向量数据库目录中检索与查询最相关的文档块并返回结构化数据。
    
    参数:
        knowledge_dir (Path): 向量数据库的本地持久化存放目录。
        query_text (str): 检索查询字符串。
        n_results (int): 检索的最相关文档块数量。
        
    返回:
        List[Dict[str, Any]]: 包含检索文档块信息的列表。
    """
    # 加载 embedding 相关的环境变量配置
    api_key, api_url, model_name = load_embedding_config()
        
    # 检查数据库目录是否存在
    if not knowledge_dir.exists():
        raise FileNotFoundError(f"Knowledge directory {knowledge_dir} does not exist.")
    
    # 获取对应的 RAG 集合
    collection = get_chroma_collection(knowledge_dir, api_key, api_url, model_name)
    
    # 在向量集合中查询最接近的 top n 个块
    results = collection.query(
        query_texts=[query_text],
        n_results=n_results
    )
    
    if not results['documents'] or not results['documents'][0]:
        return []
        
    documents = results['documents'][0]
    metadatas = results['metadatas'][0]
    distances = results['distances'][0] if 'distances' in results and results['distances'] else [None] * len(documents)
    
    output = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        output.append({
            "content": doc.strip(),
            "source": meta.get('source', 'Unknown') if meta else 'Unknown',
            "distance": dist
        })
        
    return output
