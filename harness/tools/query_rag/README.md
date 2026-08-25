# query_rag MCP

该目录提供只读 RAG MCP 服务。**当前不注册到任何 agent config**（`.mcp.json`、`.claude/settings.json`、`.codex/config.toml`、`.opencode/opencode.json`）。实现保留，供后续初始化流程按需接入。

Agent 路径已改为直接读取 `harness/knowledge/` 用户文件，方法纪律见 [`harness/rules/lca-knowledge/README.md`](../../rules/lca-knowledge/README.md)。

- main.py：注册 list_rag_libraries 和 query_rag，维护知识库白名单。
- utils/query.py：参数、schema、模型、维度和距离校验。
- utils/db.py：确认数据库文件存在后打开固定 collection。
- utils/embedding.py：从本目录 `.env` 加载 embedding 配置（不要写仓库根 `.env`）。
- tests/：无网络单元测试。

## 配置

复制 `.env.example` 为 `.env` 并填写 `EMBEDDING_API_KEY`、`EMBEDDING_API_URL`、`EMBEDDING_MODEL`。

## 启动

手动执行以下命令只会启动 stdio MCP server：

~~~bash
uv run python harness/tools/query_rag/main.py
~~~

## MCP 工具

- `list_rag_libraries()`：返回 `standards`、`openlca_manual`、`input`、`data` 的可用性、状态、chunks、embedding model 和 build ID。
- `query_rag(query, libraries, n_results, max_distance)`：`query` 非空；`libraries` 仅可为上述四类；`n_results` 为 1–50；`max_distance` 为有限非负数。

## 只读边界

调用方只能传入 standards、openlca_manual、input 或 data，不得传入本地路径。打开 Chroma 前会检查现有 chroma.sqlite3，避免在错误目录创建空数据库。

工具不负责构建、迁移、清空或修复知识库。写入入口是 `src/scripts/initialization/main.py --only rag`。

## 返回与错误

query_rag 返回结构化 results。每项包含 library、source、chunk_index、distance、content 和可用定位字段。

以下情况作为 MCP tool error 返回：

- 查询参数非法；
- 数据库缺失；
- schema 过旧；
- embedding 模型或维度不一致；
- metadata 损坏。

## 测试

~~~bash
uv run python -m unittest discover -s harness/tools/query_rag/tests -v
~~~
