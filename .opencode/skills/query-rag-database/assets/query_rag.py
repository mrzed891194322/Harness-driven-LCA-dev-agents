import argparse
from pathlib import Path
from utils import query_rag_database

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
