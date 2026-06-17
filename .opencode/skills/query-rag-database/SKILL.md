---
name: query-rag-database
description: 使用此技能并通过查询字符串查询存储在 src/knowledge/ 中的 RAG 数据库，以从嵌入的文档中检索相关信息。
---

# 查询 RAG 数据库

此技能在本地 Chroma 向量数据库中搜索与所提供查询相关的信息。

## 适用场景

当用户对已处理文档的内容提问，或明确要求“搜索 RAG 数据库”、“查询知识库”等时，使用此技能。

## 前提条件

- 必须先使用 `build-rag-database` 技能构建数据库。
- `.env` 必须配置有 `EMBEDDING_API_KEY`、`EMBEDDING_API_URL` 和 `EMBEDDING_MODEL`。

## 执行方式

运行 `assets` 文件夹中提供的 Python 脚本，并将查询字符串作为参数传递：

```bash
uv run python .opencode/skills/query_rag_database/assets/query_rag.py "在此输入您的查询内容"
```
