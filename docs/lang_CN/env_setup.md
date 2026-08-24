# 环境准备与配置

本文档介绍运行 **Harness-driven LCA Agents** 所需的环境与配置。

推荐先用命令行让 agent 做环境引导（`opencode run --command bootstrap-env`、`codex exec -s workspace-write '$bootstrap-env'` 或 `claude -p "/bootstrap-env"`）。步骤正文在 `src/scripts/setup_env/PROMPT.md`。没有 uv 时 agent 会判定不通过，需要你按下面说明手动安装。

Agent CLI（`codex` / `claude` / `opencode`）的安装与登录以各工具自己的文档为准；GUI 里只需在「设置 AI Agent 工具」中选择已安装的那一个。RAG Embedding 的填写见 [RAG 指南](rag_guide.md)。

## 1. 安装 uv

- **macOS / Linux**

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- **Windows（PowerShell）**

  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

- **验证**

  ```bash
  uv --version
  ```

## 2. Python 依赖

项目由 `.python-version` 和 `pyproject.toml` 固定使用 Python `3.14`。在项目根目录
执行：

```bash
uv sync
```

该命令会创建虚拟环境并同步依赖。

## 3. openLCA IPC

运行工作流前：

1. 启动 openLCA Desktop 并打开目标数据库。
2. 启用 IPC Server，默认地址为 `127.0.0.1:8080`。
3. 在项目根目录检查连接：

   ```bash
   uv run python src/scripts/initialization/main.py --only openlca
   ```

连接检查首次失败后会重新创建客户端并重试三次；全部失败时命令返回非零，GUI 的执行
按钮保持禁用。

截图与 GUI 外的准备步骤见[项目准备说明](project_prep.md)。
