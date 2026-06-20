# 项目目录与文件规范（总览）

> **上下文提示**：如需了解 `src/` 的内部规范，请另读同目录下的 `src-structure.md`；不要提前读取本文件全部内容。
>
> 本文件由 `project-convention` skill 维护，聚焦**项目整体结构**与**通用约定**。

---

## 1. 根目录结构

```text
.
├── .opencode/              # opencode 配置与 agent-skills
│   ├── agents/             # agent 定义文件
│   └── skills/             # 本地 skills
├── docs/                   # 全局文档与说明
├── input/                  # 外部输入目录
├── output/                 # 最终确定的交付物及对外输出
├── src/                    # 项目核心执行代码与运行状态
├── AGENT.md                # 针对所有 agent 的最高优先级行为准则
├── README.md               # 项目总说明
└── (其他环境/配置文件)       # .venv/, .env, pyproject.toml, uv.lock, .gitignore, .python-version 等

```

---

## 2. 各目录详细约定

### 2.1 `.venv/` — Python 虚拟环境

- **用途**：项目虚拟环境，由 `uv` 管理。
- **禁止**：不要在代码中硬编码虚拟环境路径；agent 应通过 `pyproject.toml` 或用户确认获取环境信息。

### 2.2 `input/` 与 `output/`

- **`input/`**：统一存放由外部用户给到的输入内容。原始数据放置在 `input/data/`，零散文件放置在 `input/files/`，全局静态知识库放置在 `input/knowledge_base/`，全局规划或外部需求文档放置在 `input/plan.md`。
- **`output/`**：只存放对外交付或最终合规验证的结果。过程中的临时文件绝不能放在此处。

### 2.3 `docs/` — 全局文档与说明

- **用途**：仓库级别的静态说明文档与知识累积。

### 2.4 `src/` — 核心代码与状态

- **详细规范**：见同目录 `src-structure.md`。编码 agent 在实现代码时，应优先阅读该文件。包含数据处理、评测、历史、执行方案（plan）、临时文件等子目录。

---

## 3. 文件操作工具选择与规范

- **读取文件**：优先使用代码编辑器提供的专门文件读取工具（如 `view_file`，`read_file`，`Read`）。
- **写入修改**：必须使用文件编辑工具进行增量修改或全量覆写。**严禁**使用 `bash` 命令行中的 `echo` 或 `cat` 等指令来直接向文件写入大段内容。

