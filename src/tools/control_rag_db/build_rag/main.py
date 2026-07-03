import sys
import argparse
from pathlib import Path

# 将 scripts 目录加入 sys.path 以使用公共的 utils
sys.path.append(str(Path(__file__).parent.parent))
# 将当前脚本目录加入 sys.path 以使用私有的 private_utils
sys.path.append(str(Path(__file__).parent))

from private_utils.builder import build_rag

def main():
    from utils.encoding import setup_io_encoding
    setup_io_encoding()

    parser = argparse.ArgumentParser(description="Build RAG database from input files.")
    parser.add_argument(
        "--input-dir", "-i",
        type=str,
        default="knowledge/inputs",
        help="Input directory containing PDF/Word/Markdown/Text files (default: knowledge/inputs)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="knowledge/rag_db",
        help="Output directory for Chroma RAG database (default: knowledge/rag_db)"
    )
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    build_rag(input_dir, output_dir)

if __name__ == "__main__":
    main()
