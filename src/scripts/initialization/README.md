# 项目初始化脚本 (initialization)

用于在项目启动阶段一次性完成两项前置准备：

1. **构建 RAG 知识库**：依据映射规则将原始文档向量化写入 Chroma 数据库。
2. **检查 openLCA IPC Server**：验证 openLCA 桌面端已启动并开启 IPC 服务。

## 目录结构

```
initialization/
├── main.py                  # 统一入口（CLI）
├── README.md                 # 本说明
├── rag_init/                 # RAG 知识库构建模块
│   ├── __init__.py
│   ├── main.py               # 构建逻辑
│   ├── mapping_rules.py      # 路径映射规则（可在此修改映射）
│   ├── config.json           # 支持转换的文档后缀配置
│   └── utils/
│       ├── __init__.py
│       ├── encoding.py       # Windows 控制台编码处理
│       ├── embedding.py      # Embedding API 环境变量加载
│       ├── file_filter.py    # 文件后缀过滤
│       ├── db.py             # ChromaDB 集合初始化
│       └── file_indexer.py   # 单文件切分与写入
└── openlca_check/            # openLCA IPC 连接检查模块
    ├── __init__.py
    ├── main.py               # 检查逻辑
    └── utils/
        ├── __init__.py
        └── encoding.py       # Windows 控制台编码处理
```

## 参考来源

- RAG 构建：`.opencode/skills/external-tools/references/query_rag_db/scripts/build_rag`
- openLCA 连接：`.opencode/skills/external-tools/references/control-openlca/scripts/utils/connection.py`
- 映射规则：`.opencode/skills/external-tools/references/query_rag_db/instruction/mapping-rules.md`

## 默认映射规则

映射规则已提取至 `rag_init/mapping_rules.py`，路径均相对于项目根目录：

| 原始输入目录 | RAG 输出目录 | 用途 |
|---|---|---|
| `knowledge/inputs/static_ref/standards` | `knowledge/rag_db/standards` | 静态：参考标准 |
| `knowledge/inputs/static_ref/openlca_manual` | `knowledge/rag_db/openlca_manual` | 静态：openLCA 使用说明 |
| `knowledge/inputs/user_file` | `knowledge/rag_db/input` | 动态：LCA 任务原始数据 |

如需调整映射，直接编辑 `rag_init/mapping_rules.py` 中的 `DEFAULT_MAPPING` 列表。

## 前置条件

1. 已配置 `.env` 中的 `EMBEDDING_API_KEY`（及可选的 `EMBEDDING_API_URL`、`EMBEDDING_MODEL`）。
2. 已安装项目依赖（`uv sync`），包含 `olca-ipc`、`chromadb`、`markitdown`、`langchain-text-splitters`、`python-dotenv`。
3. 检查 openLCA 时，需先在 openLCA 桌面端 `Tools -> Developer Tools -> IPC Server` 启动服务（默认端口 8080）。

## 使用方式

在项目根目录执行：

```bash
# 同时构建 RAG 并检查 openLCA（默认）
uv run python src/scripts/initialization/main.py

# 构建前先清空输出子目录（保留 README.md）
uv run python src/scripts/initialization/main.py --clean

# 仅构建 RAG 知识库
uv run python src/scripts/initialization/main.py --only rag

# 仅检查 openLCA 连接（自定义端口）
uv run python src/scripts/initialization/main.py --only openlca --port 8080

# 使用自定义映射 JSON 文件（格式：[{"input": "...", "output": "..."}]）
uv run python src/scripts/initialization/main.py --mapping path/to/mapping.json
```

## 单独运行子模块

```bash
# 仅检查 openLCA
uv run python src/scripts/initialization/openlca_check/main.py --port 8080
```