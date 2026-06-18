import argparse
from pathlib import Path
from utils import load_embedding_config, get_chroma_collection

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
    
    # 获取对应的 RAG 集合
    try:
        collection = get_chroma_collection(knowledge_dir, api_key, api_url, model_name)
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

def main():
    parser = argparse.ArgumentParser(description="Query RAG database.")
    parser.add_argument(
        "query",
        type=str,
        nargs="+",
        help="Query string"
    )
    parser.add_argument(
        "--db-dir", "-d",
        type=str,
        default="src/knowledge",
        help="Directory of Chroma RAG database (default: src/knowledge)"
    )
    
    args = parser.parse_args()
    
    query_text = " ".join(args.query)
    knowledge_dir = Path(args.db_dir)
    
    query_rag_database(knowledge_dir, query_text)

if __name__ == "__main__":
    main()
