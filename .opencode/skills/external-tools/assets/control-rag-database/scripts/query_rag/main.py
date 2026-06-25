import sys
import argparse
from pathlib import Path

# 将 scripts 目录加入 sys.path 以使用公共的 utils
sys.path.append(str(Path(__file__).parent.parent))
# 将当前脚本目录加入 sys.path 以使用私有的 private_utils
sys.path.append(str(Path(__file__).parent))

from private_utils.query import query_rag_database

def main():
    from utils.encoding import setup_io_encoding
    setup_io_encoding()

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
