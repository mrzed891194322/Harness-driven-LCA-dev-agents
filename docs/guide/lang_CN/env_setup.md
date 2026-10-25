# 环境准备与配置

本文档介绍运行 **Harness-driven LCA Agents** 所需的环境与配置。

在项目根目录执行（macOS、Linux 与原生 Windows 相同；Windows 可用 PowerShell 或命令提示符）。Windows 还需安装 [Git for Windows](https://git-scm.com/download/win)，供 Agent 的 bash 工具使用：

```bash
node src/scripts/start.mjs
```

该脚本每次启动前同步 uv 与 Node.js 依赖，（需要仓库根目录已有 `config.toml`），然后打开控制面板。没有 uv 或 Node.js 22+ 时会直接退出，需要你按下面说明手动安装后再运行。

Worker 固定为 **Pi SDK runtime**（`src/pi-runtime`，依赖 Node.js）。Web「设置与初始化」选择 `model_profiles.json` 中的模型档案，并为对应 Provider 填入自有 API Key（BYOK，写入 `.local/credentials/pi-auth.json`）。初始化检查探测 Node / pi-runtime 协议与 openLCA IPC，不依赖 PATH 上的 `codex` / `claude` / `opencode` / `pi` 可执行文件。主编排经 `src/backend/core/agents` → `backend.pi_client` 调用 `ModelRuntime`。业务运行只通过控制面板，不提供面向用户的命令行控制。

`config.toml` 为仓库明文配置（`gui` / `openlca` / `harness` / `pi` 段）；直接改该文件，无 example、不做 `.env` 迁移。

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

## 2. Windows：Git for Windows

从 [git-scm.com/download/win](https://git-scm.com/download/win) 安装。默认位置是 `C:\Program Files\Git\bin\bash.exe`。装到其它目录时，把 `PI_BASH` 设为该 `bash.exe` 的完整路径。Linux 和 macOS 不需要这一步。

## 3. Python 依赖

项目由 `.python-version` 和 `pyproject.toml` 固定使用 Python `3.12`。在项目根目录
执行：

```bash
uv sync
```

该命令会创建虚拟环境并同步依赖（含开发依赖 `pytest`、`ruff`、`pyright`）。另需 Node.js 22+ 与 `npm install && npm run build -w @harness/pi-runtime`。

uv 与 npm 的包缓存固定写到仓库根 `.cache/uv/`、`.cache/npm/`，由 `npm start` / `npm run dev` 自动设置。pytest / ruff 缓存分别在 `.cache/pytest/`、`.cache/ruff/`。沙箱里家目录缓存只读，不能依赖默认路径；也不要放到 `workspace/tmp/`。

开发静态检查与测试：

```bash
uv run ruff format .
uv run ruff check .
uv run pyright
uv run pytest
```

> 测试隔离：pytest 下禁止连接真实 openLCA（8080 及 `config.toml` 中的 `OPENLCA_IPC_PORT`），workspace 默认重定向到临时目录。即便如此，修改代码和跑测试请在独立 git worktree 中进行，不要在后端正在运行的主仓库里跑 pytest。

## 4. openLCA IPC

运行工作流前：

1. 启动 openLCA Desktop 并打开目标数据库。
2. 启用 IPC Server，默认地址为 `127.0.0.1:8080`。
3. 在 Web 控制面板的「设置 / 项目状态」中查看 openLCA 连通性（初始化检查失败时执行按钮保持禁用）。

![openLCA IPC Service](../assets/images/project_prep/openlca-ipc.png)

连接检查首次失败后会重新探测；环境引导（`proj_init`）也会做同一类检查，失败时记为「需你动手」。资料放入 `harness/knowledge/inputs/`、计划编写与执行前清理均在控制面板流程中完成，见根目录 `README.md`。
