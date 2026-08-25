# RAG MCP（未接入 Agent 路径）

当前 Whole-LCA / Revise-LCA **不使用 RAG**：Agent 直接读取 `harness/knowledge/` 中的用户文件，方法要求见 `harness/rules/lca-knowledge/README.md`。GUI 不再配置 Embedding，也不再构建知识库。

`harness/tools/query_rag/` 实现保留，且不注册到任何 agent config。若要单独启动该 MCP，把密钥写在 `harness/tools/query_rag/.env`（可从 `.env.example` 复制），不要写仓库根 `.env`。

```env
EMBEDDING_API_KEY="..."
EMBEDDING_API_URL="https://.../v1"
EMBEDDING_MODEL="..."
```

命令行构建遗留向量库：

```bash
uv run python src/scripts/initialization/main.py --only rag
```

构建脚本仍可能读取仓库根 `.env` 中的 Embedding 项，这是已知遗留，待后续初始化流程更新。
