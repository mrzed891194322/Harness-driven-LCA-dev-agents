# RAG 查询工具说明 (rag-query-tool.md)

此引用文件提供对本地 RAG (Retrieval-Augmented Generation，检索增强生成) 向量数据库的**查询**功能说明。

## 适用场景

当智能体需要检索特定的 LCA 标准、openLCA 操作说明或当前任务的输入数据时（读取 RAG）。

## 执行方式

在指定的本地 Chroma 向量数据库中检索与提供查询相关的信息。在检索/查询数据库前，**必须显式查阅知识库建议用途说明**：👉 [rag-knowledge-sources.md](rag-knowledge-sources.md)（说明了各个 RAG 子目录的用途，指导查询时的针对性选择）。

使用 MCP 工具进行调用：
- **工具名称**：`query_rag`
- **参数列表**：
  - `query` (str, 必填): 您的查询关键词或问题。
  - `db_dir` (str, 选填): 本地 RAG 向量数据库的目录路径（如 `"harness/knowledge/rag_db/standards"`）。
  - `n_results` (int, 选填): 返回的结果数，默认为 5。
