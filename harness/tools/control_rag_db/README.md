# RAG 数据库控制工具说明

本目录存放项目内正式的 RAG 数据库构建与查询工具。Agent 需要检索标准、openLCA 手册、用户资料或输入文件背景知识时，必须优先使用本目录下的正式工具，不得编写临时 Python 脚本。

## 工具入口

### 构建 RAG 数据库

脚本：

```bash
uv run python harness/tools/control_rag_db/build_rag/main.py --input-dir <输入目录> --output-dir <输出目录>
```

常用参数：

- `--input-dir`, `-i`：输入文档目录，默认 `harness/knowledge/inputs`
- `--output-dir`, `-o`：输出向量数据库目录，默认 `harness/knowledge/rag_db`

### 查询 RAG 数据库

脚本：

```bash
uv run python harness/tools/control_rag_db/query_rag/main.py "<查询内容>" --db-dir <RAG数据库目录>
```

常用参数：

- `query`：查询文本，可包含多个词，脚本会合并为完整查询语句
- `--db-dir`, `-d`：目标 RAG 数据库目录，默认 `harness/knowledge/rag_db`

## 约束

- 所有 Python 命令必须使用 `uv run python ...`。
- 禁止为一次性检索、数据探查或格式转换创建临时脚本。
- 如工具能力不足，只能扩展本目录下的正式工具，并同步更新本 README。
