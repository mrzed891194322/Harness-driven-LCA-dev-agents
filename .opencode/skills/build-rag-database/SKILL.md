---
name: build-rag-database
description: 使用此技能将 input/ 目录中的文件通过 markitdown 转换为 markdown，然后将其嵌入（embeddings）存储在 src/knowledge/ 的 Chroma RAG 数据库中。
---

# 构建 RAG 数据库

此技能将原始文件转换为 markdown 格式，并将其嵌入（embeddings）存储在向量数据库中。

## 适用场景

当用户要求“构建 RAG 数据库”、“处理输入文件”或将 `input/` 目录转换为 `src/knowledge/` 中的向量数据库时，使用此技能。

## 前提条件

- 确保已安装所需的 Python 包（`markitdown`, `chromadb`, `openai`, `langchain`, `python-dotenv`）。
- 确保 `.env` 文件中配置了 `EMBEDDING_API_KEY`、`EMBEDDING_API_URL` 和 `EMBEDDING_MODEL`。

## 执行方式

运行 `assets` 文件夹中提供的 Python 脚本：

```bash
uv run python .opencode/skills/build_rag_database/assets/build_rag.py
```
