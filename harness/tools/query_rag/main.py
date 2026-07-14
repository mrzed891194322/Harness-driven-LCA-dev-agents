import sys
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# 将当前目录（query_rag）加入 sys.path 以正常加载 utils 包中的组件
sys.path.append(str(Path(__file__).parent))

from utils.query import retrieve_rag_chunks

# 初始化 FastMCP 实例
mcp = FastMCP("LCA-RAG-Helper")

@mcp.tool()
def query_rag(query: str, db_dir: str = "harness/knowledge/rag_db", n_results: int = 5) -> str:
    """
    Query the RAG (Retrieval-Augmented Generation) database to retrieve relevant chunks 
    about life cycle assessment (LCA), background data, or process descriptions.

    :param query: The search query string.
    :param db_dir: The relative directory of Chroma RAG database (default: harness/knowledge/rag_db).
    :param n_results: Number of top relevant results to retrieve.
    """
    knowledge_dir = Path(db_dir)
    try:
        results = retrieve_rag_chunks(knowledge_dir, query, n_results)
    except Exception as e:
        return f"Error querying RAG database: {str(e)}"
        
    if not results:
        return "No relevant results found in the database."
        
    # 格式化输出供 LLM 读取
    formatted_output = []
    for i, res in enumerate(results):
        dist_str = f" (Distance: {res['distance']:.4f})" if res['distance'] is not None else ""
        formatted_output.append(
            f"--- Result {i+1} [Source: {res['source']}]{dist_str} ---\n"
            f"{res['content']}\n"
            f"{'-'*50}"
        )
    return "\n\n".join(formatted_output)

if __name__ == "__main__":
    # 启动 MCP 服务端（默认使用 stdio 协议通信）
    mcp.run()
