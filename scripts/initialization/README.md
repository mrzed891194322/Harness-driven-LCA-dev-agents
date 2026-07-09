# 项目初始化脚本 (initialization)

用于在项目启动阶段完成初始化前置准备：

1. **检查环境**：验证 `opencode` CLI 与 RAG embedding API 可用。
2. **构建 RAG 知识库**：依据映射规则将原始文档向量化写入 Chroma 数据库。
3. **检查 openLCA IPC Server**：验证 openLCA 桌面端已启动并开启 IPC 服务。

## 目录结构

```
initialization/
├── main.py                  # 统一入口（CLI）
├── README.md                 # 本说明
├── clean_dir/                # 目录清理模块
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   └── utils/
│       ├── __init__.py
│       └── clean.py
├── env_check/                # 环境检查模块
│   ├── __init__.py
│   └── main.py
├── rag_init/                 # RAG 知识库构建模块
│   ├── __init__.py
│   ├── main.py               # 构建逻辑
│   ├── mapping_rules.py      # 路径映射规则（可在此修改映射）
│   └── private_utils/
│       ├── __init__.py
│       ├── embedding.py      # Embedding API 环境变量加载
│       ├── file_filter.py    # 文件后缀过滤
│       ├── db.py             # ChromaDB 集合初始化
│       ├── builder.py         # RAG 构建流程
│       ├── file_indexer.py   # 单文件切分与写入
│       └── config.json       # 支持转换的文档后缀配置
├── utils/
│   ├── __init__.py
│   └── encoding.py           # Windows 控制台编码处理
└── openlca_check/            # openLCA IPC 连接检查模块
    ├── __init__.py
    └── main.py               # 检查逻辑
```

`scripts/initialization` 内部已自包含目录清理、RAG 构建和 openLCA 连接检查实现，不再调用 `harness/tools` 下的工具脚本。文件同步仍保持为独立脚本：`scripts/file_sync/main.py`。

## 默认映射规则

映射规则已提取至 `rag_init/mapping_rules.py`，路径均相对于项目根目录：

| 原始输入目录 | RAG 输出目录 | 用途 |
|---|---|---|
| `harness/knowledge/inputs/static_ref/standards` | `harness/knowledge/rag_db/standards` | 静态：参考标准 |
| `harness/knowledge/inputs/static_ref/openlca_manual` | `harness/knowledge/rag_db/openlca_manual` | 静态：openLCA 使用说明 |
| `harness/knowledge/inputs/user_file` | `harness/knowledge/rag_db/input` | 动态：LCA 任务原始数据 |

如需调整映射，直接编辑 `rag_init/mapping_rules.py` 中的 `DEFAULT_MAPPING` 列表。

## 前置条件

1. 已配置 `.env` 中的 `EMBEDDING_API_KEY`（及可选的 `EMBEDDING_API_URL`、`EMBEDDING_MODEL`）。
2. 已安装项目依赖（`uv sync`），包含 `olca-ipc`、`chromadb`、`markitdown`、`langchain-text-splitters`、`python-dotenv`。
3. 检查 openLCA 时，需先在 openLCA 桌面端 `Tools -> Developer Tools -> IPC Server` 启动服务（默认端口 8080）。

## 使用方式

在项目根目录执行：

```bash
# manual 模式（默认）：先清理目录并调用独立的 file_sync，再检查环境、构建 RAG、检查 openLCA
uv run python scripts/initialization/main.py

# gui 模式：只检查环境、构建 RAG、检查 openLCA
uv run python scripts/initialization/main.py --mode gui

# 构建前先清空输出子目录（保留 README.md）
uv run python scripts/initialization/main.py --clean

# 仅清理目录
uv run python scripts/initialization/main.py --only clean

# 仅检查环境
uv run python scripts/initialization/main.py --only env

# 仅构建 RAG 知识库
uv run python scripts/initialization/main.py --only rag

# 仅检查 openLCA 连接（自定义端口）
uv run python scripts/initialization/main.py --only openlca --port 8080

# 使用自定义映射 JSON 文件（格式：[{"input": "...", "output": "..."}]）
uv run python scripts/initialization/main.py --mapping path/to/mapping.json
```

## 单独运行子模块

```bash
# 仅检查 openLCA
uv run python scripts/initialization/openlca_check/main.py --port 8080
```
