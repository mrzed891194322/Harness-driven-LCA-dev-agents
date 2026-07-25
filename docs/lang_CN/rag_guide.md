# RAG 数据库构建与查询指南

本项目使用 ChromaDB 与 OpenAI 兼容 embedding API。

- 写入：`src/scripts/initialization/main.py`
- 查询：query_rag MCP（由 opencode 配置调用）

## 知识库类型

| library | 内容 |
| :--- | :--- |
| standards | LCA 标准与规范 |
| openlca_manual | openLCA 操作资料 |
| input | 用户参考文档 |
| data | 用户表格和结构化参考数据 |

## 构建

```bash
uv run python src/scripts/initialization/main.py --only rag
```

## 查询

RAG 由 opencode 通过 `query_rag` MCP 工具提供查询能力，示例参数见下文。

可用参数示例：

```json
{
  "query": "openLCA 如何设置过程分配",
  "libraries": ["openlca_manual"],
  "n_results": 5,
  "max_distance": 0.9
}
```

## 配置

```env
EMBEDDING_API_KEY="..."
EMBEDDING_API_URL="https://.../v1"  # 可选
EMBEDDING_MODEL="..."
```

修改 `EMBEDDING_MODEL` 后请重建知识库。

支持的文件格式定义见：`src/scripts/initialization/rag_init/private_utils/config.json`。

## 测试

```bash
uv run python -m unittest discover -s src/scripts/initialization/rag_init/tests -v
uv run python -m unittest discover -s harness/tools/query_rag/tests -v
```
