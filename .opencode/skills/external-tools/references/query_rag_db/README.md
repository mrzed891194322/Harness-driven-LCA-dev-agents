# RAG 数据库查询 (query_rag_db)

此引用文件提供对本地 RAG (Retrieval-Augmented Generation，检索增强生成) 向量数据库的**查询**功能说明。

## 适用场景

当智能体需要检索特定的 LCA 标准、openLCA 操作说明或当前任务的输入数据时（读取 RAG）。

## 执行方式

在指定的本地 Chroma 向量数据库中检索与提供查询相关的信息。在检索/查询数据库前，**必须显式查阅知识库建议用途说明**：👉 [knowledge-sources.md](knowledge-sources.md)（说明了各个 RAG 子目录的用途，指导查询时的针对性选择）。

运行命令示例：
```bash
uv run python src/tools/control_rag_db/query_rag/main.py "您的查询关键词或问题" --db-dir <RAG数据库目录>
```
