# 项目目录与文件规范（总览）

> **上下文提示**：如需了解 `src/` 与 `workspace/` 的内部规范，请另读同目录下的 `src-structure.md`；不要提前读取本文件全部内容。
>
> 本文件由 `project-regulation` skill 维护，聚焦**项目整体结构**与**通用约定**。

---

## 1. 根目录结构

```text
.
├── .opencode/              # opencode 配置与 agent-skills
│   ├── agents/             # agent 定义文件
│   └── skills/             # 本地 skills
├── docs/                   # 全局文档与说明
├── knowledge/              # 知识库主目录
│   ├── inputs/             # 原始输入文件与静态标准
│   │   ├── static_ref/     # 全局静态参考知识库（如标准文件等）
│   │   ├── user_data/      # 原始上传数据目录
│   │   └── user_file/      # 零散上传文件目录
│   └── rag_db/             # 动态转换生成的 RAG 向量数据库
├── src/                    # 项目核心执行代码目录
├── workspace/              # 项目运行工作区与运行状态目录
├── AGENT.md                # 针对所有 agent 的最高优先级行为准则
├── README.md               # 项目总说明
└── (其他环境/配置文件)       # .venv/, .env, pyproject.toml, uv.lock, .gitignore, .python-version 等

```

---

## 2. 各目录详细约定

### 2.1 `.venv/` — Python 虚拟环境

- **用途**：项目虚拟环境，由 `uv` 管理。
- **禁止**：不要在代码中硬编码虚拟环境路径；agent 应通过 `pyproject.toml` 或用户确认获取环境信息。

### 2.2 `knowledge/`
- **`knowledge/inputs/`**：统一存放由外部用户给到的输入内容。原始上传数据放置在 `knowledge/inputs/user_data/`，零散上传文件放置在 `knowledge/inputs/user_file/`，全局静态知识库放置在 `knowledge/inputs/static_ref/`，全局规划或外部需求文档放置在 `knowledge/plan.md`。
- **`knowledge/rag_db/`**：存放向量数据库。

### 2.3 `docs/` — 全局文档与说明
- **用途**：仓库级别的静态说明文档与知识累积。

### 2.4 `src/` — 核心代码
- **详细规范**：见同目录 `src-structure.md`。包含 GUI、项目规则/规范、各种处理脚本等。

### 2.5 `workspace/` — 项目运行工作区
- **详细规范**：见同目录 `src-structure.md`。包含当前执行中的内部设计方案 (plan)、数据清洗的脚本及产生的中间数据 (data)、LCI 数据 (LCI)、运行日志 (logs)、记忆存储 (memory)、报告 (report) 和临时文件 (tmp)。

---

## 3. 文件操作工具选择与规范

- **读取文件**：优先使用代码编辑器提供的专门 file 读取工具（如 `view_file`，`read_file`，`Read`）。
- **写入修改**：必须使用文件编辑工具进行增量修改或全量覆写。**严禁**使用 `bash` 命令行中的 `echo` 或 `cat` 等指令来直接向文件写入大段内容。
