# 📂 RAG 数据库构建与查询指南

本文档详细介绍了本项目中 **RAG (Retrieval-Augmented Generation，检索增强生成)** 数据库的构建、读取/查询方式，以及不同的触发和执行途径。

---

## 💡 RAG 系统概述

本项目使用 **ChromaDB** 作为本地向量数据库（Collection 名称为 `rag_collection`），并结合 **Embedding 模型** 实现知识检索。
- **文本提取与转换**：采用 Microsoft 的 `markitdown` 将各类源文件（PDF、Word、Excel、CSV 等）在源目录下转换为 `.md` 文件，随后系统统一读取并提取所有 `.md` 文件的文本内容。对于图片等非文本文件，`markitdown` 会记录其相对路径，确保 RAG 系统在检索时能关联引用文件。
- **文本分块**：采用 LangChain 的 `RecursiveCharacterTextSplitter`，分块大小（`chunk_size`）为 1000 字符，重叠大小（`chunk_overlap`）为 200 字符。
- **Embedding API**：通过配置 `.env` 环境变量中的 API Key 与 API Base 支持任意 OpenAI 兼容的 Embedding 接口。

---

## 🛠️ 构建/初始化 RAG 数据库

构建 RAG 数据库用于将源文档处理并写入本地向量库。目前项目提供了以下三种方式进行构建：

### 方式一：通过 OpenCode Command (推荐)
在命令行中直接运行项目预设的 OpenCode 命令。该命令会自动清空 `src/knowledge/` 目录（保留 `README.md`），并将标准知识库和输入文件目录进行处理：
```bash
opencode run --command init-rag-database
```
*执行逻辑参见 [.opencode/commands/init-rag-database.md](../.opencode/commands/init-rag-database.md)*。

### 方式二：通过与 Agent 交互
您可以直接在 OpenCode 客户端中以自然语言对 Agent 下达指令。下达指令时，请注意**指明文件来源目录与目标输出目录**。例如：
- *“帮我把 `input/knowledge_base/standards` 目录下的文件构建并写入到 `src/knowledge/standards` RAG 数据库”*
- *“处理 `input/files` 文件夹中的输入文件并写入到 `src/knowledge/input` 中”*
- *“初始化 LCA 知识库，输入目录为 `input/`，输出目录为 `src/knowledge/`”*

Agent 会根据您的指令识别意图及路径参数，自动调用相应的 `build-rag-database` 技能在指定的目标目录下构建向量数据库。

### 方式三：直接运行 Python 脚本
若需要在项目虚拟环境中进行更灵活的参数配置，可直接运行 Python 脚本：
```bash
uv run python .opencode/skills/build-rag-database/assets/build_rag.py --input-dir <输入目录路径> --output-dir <输出目录路径>
```
**常用参数**：
- `--input-dir` 或 `-i`：存放原始文档的输入目录（默认值为 `input`）。
- `--output-dir` 或 `-o`：存放向量数据库的输出目录（默认值为 `src/knowledge`）。

---

## 🔍 读取/查询 RAG 数据库

在大多数情况下，工作流中的智能体（Agent）会自动使用 [query-rag-database](../.opencode/skills/query-rag-database) 技能读取 RAG 数据库。

如果用户想要主动了解 RAG 数据库中的内容，或者指导 Agent 进一步利用 RAG 知识开展工作，可以通过以下方式进行：

### 方式一：通过文字指令与 Agent 交互 (推荐)
您可以直接向 Agent 发送提问或检索指令。例如：
- *“在数据库里帮我搜索关于 LCA 合规性的要求”*
- *“查询一下知识库中关于 Scope 3 碳排放的定义”*

Agent 会识别您的意图，自动调用 `query-rag-database` 技能进行知识检索，并结合检索结果回答您的问题或执行后续任务。

### 方式二：直接运行 Python 脚本
您也可以直接在终端运行查询脚本，传入查询字符串以手动检索数据库内容：
```bash
uv run python .opencode/skills/query-rag-database/assets/query_rag.py "您的查询关键词或问题" --db-dir <RAG数据库目录>
```
**常用参数**：
- `--db-dir` 或 `-d`：要查询的 RAG 数据库目录（默认值为 `src/knowledge`）。
- *示例*：
  ```bash
  uv run python .opencode/skills/query-rag-database/assets/query_rag.py "生命周期评价标准" --db-dir src/knowledge/standards
  ```


---

## ⚙️ 核心配置文件与环境变量

运行 RAG 相关脚本前，请确保已正确配置了本地环境变量。具体配置步骤与典型服务商案例请参考 [`环境准备与配置详解`文档](env_setup.md#5-可选服务商配置案例)。

1. **`.env` 文件配置**：
   ```env
   EMBEDDING_API_KEY="您的 API 密钥"
   EMBEDDING_API_URL="您的 API 接口地址"
   EMBEDDING_MODEL="使用的 Embedding 模型名称"
   ```
2. **支持的文件格式**：
   支持的文件类型由 [.opencode/skills/build-rag-database/assets/config.json](../.opencode/skills/build-rag-database/assets/config.json) 中的 `supported_file_types` 列表定义。默认支持 `.pdf`、`.docx`、`.doc`、`.md`、`.txt`、`.xlsx`、`.xls`、`.csv`、`.json`、`.xml`、`.html`、`.pptx`、`.epub` 等格式。
