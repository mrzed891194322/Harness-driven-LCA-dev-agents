# Multi-Agent LCA Orchestrator (202606-harness-agent-lca)

这是一个使用多智能体（Multi-agent）在 harness 框架下进行合规化 **LCA（Life Cycle Assessment，生命周期评价）** 输出的项目。

## 🚀 环境配置

请按以下步骤配置运行环境：

1. **准备工具**：安装 [uv](https://github.com/astral-sh/uv) (Python 包管理工具) 和 [OpenCode](https://opencode.ai/)。
2. **配置 OpenCode**：运行 `opencode auth login` 或使用 `/connect` 命令登录并添加您的 API Provider 密钥。
3. **添加虚拟环境**：在项目根目录下运行 `uv sync` 自动创建虚拟环境并同步项目依赖。
4. **配置环境变量**：复制并配置本地 `.env` 文件（用于配置 Embedding 模型的 API 环境变量，参考 [.env.example](.env.example)）。


> 💡 **详细的安装、配置指南请参考**：[环境准备与配置详解](docs/setup_guide.md)

---

## 🛠️ 项目准备

1. **构建 RAG 数据库**：首先执行以下命令构建 RAG 数据库：
   ```bash
   opencode run --command init-rag-database
   ```

---


