import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import chromadb
import chromadb.utils.embedding_functions as embedding_functions

def main():
    if len(sys.argv) < 2:
        print("Usage: uv run python query_rag.py \"<query_string>\"")
        return
        
    query_text = " ".join(sys.argv[1:])
    
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("EMBEDDING_API_KEY")
    api_url = os.getenv("EMBEDDING_API_URL")
    model_name = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    
    if not api_key or api_key == "sk-your-api-key-here":
        print("Error: Please set a valid EMBEDDING_API_KEY in .env")
        return
        
    knowledge_dir = Path("src/knowledge")
    
    if not knowledge_dir.exists():
        print(f"Error: Knowledge directory {knowledge_dir} does not exist. Please run the build_rag_database skill first.")
        return
        
    print(f"Initializing ChromaDB...")
    client = chromadb.PersistentClient(path=str(knowledge_dir))
    
    # Configure OpenAI embedding function
    kwargs = {"api_key": api_key, "model_name": model_name}
    if api_url:
        kwargs["api_base"] = api_url
        
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(**kwargs)
    
    try:
        collection = client.get_collection(name="rag_collection", embedding_function=openai_ef)
    except Exception as e:
        print(f"Error getting collection 'rag_collection': {e}")
        return
        
    print(f"\nSearching for: '{query_text}'\n")
    
    # Perform search
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
    
    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        source = meta.get('source', 'Unknown') if meta else 'Unknown'
        distance_str = f" (Distance: {dist:.4f})" if dist is not None else ""
        print(f"--- Result {i+1} [Source: {source}]{distance_str} ---")
        print(doc.strip())
        print("-" * 50 + "\n")

if __name__ == "__main__":
    main()
