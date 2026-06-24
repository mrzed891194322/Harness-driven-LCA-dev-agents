# Harness-driven LCA agents project

这是一个使用多智能体（Multi-agent）在 harness 框架下进行合规化 **LCA（Life Cycle Assessment，生命周期评价）** 输出的项目。

## 🚀 环境配置

请按以下步骤配置运行环境：

1. **准备工具**：安装 [uv](https://github.com/astral-sh/uv) (Python 包管理工具) 和 [OpenCode](https://opencode.ai/)。
2. **配置 OpenCode 与 Agent 模型**：运行 `opencode auth login` 或使用 `/connect` 命令登录并添加 API 提供商密钥，并在 [.opencode/opencode.json](.opencode/opencode.json) 中为每个 Agent 配置合适的模型。
3. **添加虚拟环境**：在项目根目录下运行 `uv sync` 自动创建虚拟环境并同步项目依赖。
4. **配置环境变量**：复制并配置本地 `.env` 文件（用于配置 Embedding 模型的 API 环境变量，参考 [.env.example](.env.example)）。


> 💡 **详细的安装、配置指南请参考**：[环境准备与配置详解](docs/env_setup.md)

---

## 🛠️ 项目准备

请在每次运行具体任务前，确保按以下顺序完成项目准备：

1. **准备输入文件**：在 [input/](input/) 目录下放置您的参考文档（如环评报告），并根据模板 [docs/assets/templates/plan.md](docs/assets/templates/plan.md) 编写或更新 LCA 计划需求文件。
2. **开启 openLCA IPC Server**：打开 openLCA 桌面客户端，并确保开启了 IPC Server 服务（默认端口 8080）。
3. **构建 RAG 数据库**：在终端运行 `opencode run --command init-rag-database`，或在 OpenCode CLI/desktop 中直接输入 `/init-rag-database`，以执行 RAG 数据库构建。

> 💡 **详细的项目准备步骤请参考**：[项目准备说明文档](docs/project_prep.md)

---

## 🚀 任务执行

项目支持以下两种途径开展 LCA 评估任务：

### 途径一：利用预设命令逐步执行（推荐）
通过执行以下预设 OpenCode 命令（或在 OpenCode 交互界面直接输入对应快捷指令）分布完成任务：
* **制定 LCA 计划**：运行 `make-plan` 任务
* **设计与构建 LCI 模型**：运行 `design-lci` 任务
* **导入数据至 openLCA**：运行 `import-lci` 任务

> 💡 **常用快捷指令及脚本操作详见**：[常用指令与提示词](docs/常用指令与提示词.md)

### 途径二：主智能体自主编排与串联（开发中，尚未成熟）
您可以在 OpenCode 客户端直接向主智能体（`major-orchestrator`）以自然语言布置总任务。主智能体会尝试自主规划并串联各子智能体完成整个 LCA 评估链路。
*(注：该方式目前仍处于开发与调优阶段。)*
