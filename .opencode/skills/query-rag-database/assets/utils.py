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

def query_rag_database(knowledge_dir: Path, query_text: str):
    """
    在指定的 Chroma 向量数据库目录中检索与查询最相关的文档块并打印结果。
    
    参数:
        knowledge_dir (Path): 向量数据库的本地持久化存放目录。
        query_text (str): 检索查询字符串。
    """
    # 加载 embedding 相关的环境变量配置
    try:
        api_key, api_url, model_name = load_embedding_config()
    except ValueError as e:
        print(f"Error: {e}")
        return
        
    # 检查数据库目录是否存在
    if not knowledge_dir.exists():
        print(f"Error: Knowledge directory {knowledge_dir} does not exist. Please run the build_rag_database skill first.")
        return
        
    print(f"Initializing ChromaDB at {knowledge_dir}...")
    client = chromadb.PersistentClient(path=str(knowledge_dir))
    
    # 配置 OpenAI 嵌入函数
    kwargs = {"api_key": api_key, "model_name": model_name}
    if api_url:
        kwargs["api_base"] = api_url
        
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(**kwargs)
    
    # 获取对应的 RAG 集合
    try:
        collection = client.get_collection(name="rag_collection", embedding_function=openai_ef)
    except Exception as e:
        print(f"Error getting collection 'rag_collection': {e}")
        return
        
    print(f"\nSearching for: '{query_text}'\n")
    
    # 在向量集合中查询最接近的 top 5 个块
    results = collection.query(
        query_texts=[query_text],
        n_results=5
    )
    
    if not results['documents'] or not results['documents'][0]:
        print("No results found.")
        return
        
    documents = results['documents'][0]
    metadatas = results['metadatas'][0]
    distances = results['distances'][0] if 'distances' in results and results['distances'] else [None] * len(documents)
    
    print(f"Found {len(documents)} relevant chunks:\n")
    
    # 输出每一个相关文本块的内容及相关元数据
    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        source = meta.get('source', 'Unknown') if meta else 'Unknown'
        distance_str = f" (Distance: {dist:.4f})" if dist is not None else ""
        print(f"--- Result {i+1} [Source: {source}]{distance_str} ---")
        print(doc.strip())
        print("-" * 50 + "\n")
