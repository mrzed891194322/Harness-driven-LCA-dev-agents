---
name: control-rag-database
description: 使用此技能操控 RAG 向量数据库。支持数据库的构建/初始化（写入 RAG），以及在指定的 Chroma 数据库中查询与检索信息（读取 RAG）。
---

# RAG 数据库操控 (control-rag-database)

此技能提供对本地 RAG (Retrieval-Augmented Generation，检索增强生成) 向量数据库的构建与查询功能。

## 适用场景

1. **构建与初始化数据库**：当需要处理输入文档、背景标准或对特定 LCA 任务的原始文件进行向量化处理时（写入 RAG）。
2. **查询与检索数据库**：当智能体需要检索特定的 LCA 标准、操作说明或任务输入信息来生成计划和模型时（读取 RAG）。


## 执行方式

通过运行 `scripts` 文件夹下提供的专用 Python 脚本来完成对应的 RAG 需求。

### 1. 构建 RAG 数据库（写入）
将指定输入目录中各种支持的文档和数据文件提取文本并嵌入，存储到指定的 Chroma 数据库目录中。在构建或更新数据库（写入）前，**必须显式查阅并遵循路径映射规则**：👉 [assets/mapping-rules.md](assets/mapping-rules.md) （规定了静态背景知识、动态 LCA 数据输入在转化为 RAG 数据库时的具体目标子目录）。

运行命令示例：
```bash
uv run python .opencode/skills/control-rag-database/scripts/build_rag/main.py --input-dir <输入目录路径> --output-dir <输出目录路径>
```

### 2. 查询 RAG 数据库（读取）
在指定的本地 Chroma 向量数据库中检索与提供查询相关的信息。在检索/查询数据库（读取）前，**必须显式查阅并遵循知识库建议用途说明**：👉 [assets/knowledge-sources.md](assets/knowledge-sources.md) （说明了各个输出 RAG 子目录的用途，指导查询检索时的针对性选择）。

运行命令示例：
```bash
uv run python .opencode/skills/control-rag-database/scripts/query_rag/main.py "您的查询关键词或问题" --db-dir <RAG数据库目录>
```
