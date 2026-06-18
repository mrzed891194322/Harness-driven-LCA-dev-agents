---
name: build-rag-database
description: 使用此技能将指定输入目录中的 PDF、Word、Markdown 和文本文件等通过 markitdown 处理并提取文本，然后将其嵌入（embeddings）存储在指定输出目录的 Chroma RAG 数据库中。
---

# 构建 RAG 数据库

此技能将原始文件（支持 PDF、Word、Markdown 及 TXT 文本等类型）转换为 Markdown 格式或直接提取文本，并将其嵌入（embeddings）存储在向量数据库中。其他类型的文件（如图片）不进行转化，但如果在md中引用则会记录文件路径。

## 适用场景

当用户要求“构建 RAG 数据库”、“处理输入文件”或将指定目录转换为指定输出目录中的向量数据库时，使用此技能。

## 前提条件

- 确保已安装所需的 Python 包（`markitdown`, `chromadb`, `openai`, `langchain`, `python-dotenv`）。
- 确保 `.env` 文件中配置了 `EMBEDDING_API_KEY`、`EMBEDDING_API_URL` 和 `EMBEDDING_MODEL`。

## 执行方式

运行 `assets` 文件夹中提供的 Python 脚本，支持通过外部参数 `--input-dir`（或 `-i`）指定输入目录，以及 `--output-dir`（或 `-o`）指定输出目录：

```bash
uv run python .opencode/skills/build-rag-database/assets/build_rag.py --input-dir <输入目录路径> --output-dir <输出目录路径>
```

