# 环境准备与配置

本文档介绍运行 **Harness-driven LCA Agents** 所需的环境与配置。

推荐先用命令行让 agent 做环境引导（`opencode run --command bootstrap-env`、`codex exec -s workspace-write '$bootstrap-env'` 或 `claude -p "/bootstrap-env"`）。步骤正文在 `src/scripts/setup_env/PROMPT.md`。没有 uv 时 agent 会判定不通过，需要你按下面说明手动安装。

## 1. 运行依赖

项目需要 uv、OpenCode、可用的模型服务，以及能够访问 OpenAI 兼容
Embedding API 的配置。

### 1.1 安装 uv

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

### 1.2 安装 OpenCode

推荐使用 npm 全局安装：

```bash
npm install -g opencode-ai
```

也可以按照 OpenCode 官方文档选择其他安装方式。

验证安装：

```bash
opencode --version
```

## 2. OpenCode 与 Agent 配置

### 2.1 认证与登录

- 运行 `opencode auth login`。
- 或在 OpenCode 交互界面中使用 `/connect` 配置服务商。

### 2.2 模型与项目配置

- 核心配置文件是 [`.opencode/opencode.json`](../../.opencode/opencode.json)。
- 确认 `major-orchestrator`、`sub-executor` 和 `eval-reviewer` 配置的模型在当前
  OpenCode 服务商中可用。
- 核心流程 Agent 建议使用质量和稳定性较高的模型；不同角色可以按成本与能力调整。

## 3. Python 与环境变量

项目由 `.python-version` 和 `pyproject.toml` 固定使用 Python `3.14`。在项目根目录
执行：

```bash
uv sync
```

该命令会创建虚拟环境并同步依赖。`src/scripts/initialization/main.py` 会进一步检查
运行环境。

### 3.1 Embedding 环境变量

复制 `.env.example` 到 `.env`：

```bash
cp .env.example .env
```

Windows 命令提示符可使用：

```bat
copy .env.example .env
```

填写 Embedding 服务配置：

```env
EMBEDDING_API_KEY="your-api-key"
EMBEDDING_API_URL="https://example.com/v1"
EMBEDDING_MODEL="your-embedding-model"
```

`EMBEDDING_API_URL` 应指向兼容 OpenAI API 的服务地址。变更模型后必须重新构建 RAG
知识库；构建端和查询端使用的模型名及向量维度必须一致。

## 4. openLCA IPC

运行工作流前：

1. 启动 openLCA Desktop 并打开目标数据库。
2. 启用 IPC Server，默认地址为 `127.0.0.1:8080`。
3. 在项目根目录检查连接：

   ```bash
   uv run python src/scripts/initialization/main.py --only openlca
   ```

连接检查首次失败后会重新创建客户端并重试三次；全部失败时命令返回非零，GUI 的执行
按钮保持禁用。

完整准备步骤见[项目准备说明](project_prep.md)。
