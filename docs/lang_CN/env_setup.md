# 环境准备与配置

本文档介绍运行 **Harness-driven LCA Agents** 所需的环境与配置。

开箱后，在项目根目录执行 `uv sync` 即可安装依赖。各 worker 的安装与登录以各自文档为准。

主编排与 GUI 初始化检查走 `src/scripts/agent_sdk/providers/<name>/`：`openai-codex` / `claude-agent-sdk` / `opencode-ai` / `deepseek-harness-sdk` / `google-antigravity`。GUI「初始化检查」会对所选 worker 发一条短 ping。opencode 还需 PATH 上的 `opencode` 或已设 `OPENCODE_BASE_URL`，以及 `OPENCODE_PROVIDER` / `OPENCODE_MODEL`；antigravity 需要 `GEMINI_API_KEY` 或 Vertex 凭据。走 GUI 时，在「设置 AI Agent 工具」中选择可用的 worker。

可选环境诊断：

```bash
uv run python src/scripts/check_status/main.py
```

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

项目由 `.python-version` 和 `pyproject.toml` 固定使用 Python `3.12`。在项目根目录
执行：

```bash
uv sync
```

该命令会创建虚拟环境并同步依赖（含开发依赖 `pytest`）。

## 3. openLCA IPC

运行工作流前：

1. 启动 openLCA Desktop 并打开目标数据库。
2. 启用 IPC Server，默认地址为 `127.0.0.1:8080`。
3. 在项目根目录检查连接：

   ```bash
   uv run python src/scripts/check_status/main.py --only openlca
   ```

![openLCA IPC Service](../assets/images/project_prep/openlca-ipc.png)

连接检查首次失败后会重新创建客户端并重试三次；全部失败时命令返回非零，GUI 的执行
按钮保持禁用。

## 4. 无 GUI 运行 LCA 前的清理

不使用 GUI 时，在运行 Python 主编排之前执行：

```bash
uv run python src/scripts/clean_dir/main.py -y --preset whole-lca
# 或 revise-lca：--preset revise-lca（不清理 workspace）
```

然后手工复制资料到 `harness/knowledge/`，并编写 `workspace/inputs/plan.md`（或 `revise.md`）。详见根目录 `README.md` 与 `src/scripts/clean_dir/README.md`。
