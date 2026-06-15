import os
from pathlib import Path
from dotenv import load_dotenv
from markitdown import MarkItDown
import chromadb
import chromadb.utils.embedding_functions as embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter

def main():
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("EMBEDDING_API_KEY")
    api_url = os.getenv("EMBEDDING_API_URL")
    model_name = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    
    if not api_key or api_key == "sk-your-api-key-here":
        print("Error: Please set a valid EMBEDDING_API_KEY in .env")
        return
        
    input_dir = Path("input")
    knowledge_dir = Path("src/knowledge")
    
    # Ensure directories exist
    input_dir.mkdir(exist_ok=True)
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Initializing MarkItDown...")
    md = MarkItDown()
    
    print(f"Initializing ChromaDB...")
    client = chromadb.PersistentClient(path=str(knowledge_dir))
    
    # Configure OpenAI embedding function
    kwargs = {"api_key": api_key, "model_name": model_name}
    if api_url:
        kwargs["api_base"] = api_url
        
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(**kwargs)
    
    # Get or create collection
    collection = client.get_or_create_collection(
        name="rag_collection", 
        embedding_function=openai_ef
    )
    
    # Setup text splitter from langchain-text-splitters
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    
    # Find files to process
    files = list(input_dir.rglob("*"))
    valid_files = [f for f in files if f.is_file() and not f.name.startswith('.')]
    
    if not valid_files:
        print("No files found in input/")
        return
        
    for file_path in valid_files:
        print(f"Processing {file_path}...")
        try:
            # Convert file to markdown
            result = md.convert(str(file_path))
            text_content = result.text_content
            
            # Split text into chunks
            chunks = text_splitter.split_text(text_content)
            
            # Prepare data for ChromaDB
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
                
            # Add to vector store
            if documents:
                collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids
                )
                print(f"Added {len(documents)} chunks from {file_path}")
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            
    print("RAG database build completed successfully.")

if __name__ == "__main__":
    main()
