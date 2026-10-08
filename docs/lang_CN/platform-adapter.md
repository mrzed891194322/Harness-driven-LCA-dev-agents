# 运行入口

同一套 Whole-LCA 契约只在 `harness/`。Python 主编排器是唯一运行入口。项目 MCP 由 `harness/LCA-main.yaml` 注册，经 `src/backend/core/agents` 会话接口注入任务会话。Worker 为项目内 **Pi SDK runtime**（`src/backend/pi-runtime`），不再依赖 PATH 上的 `codex` / `claude` / `opencode` / `pi` CLI。

## 用户入口

```bash
pnpm dev   # Next.js + FastAPI（见根目录 README）
uv run python src/backend/scripts/workflow.py --workflow harness/LCA-main.yaml
uv run python src/backend/scripts/workflow.py --workflow harness/LCA-revise.yaml
```

环境引导：读取并执行 `src/backend/scripts/proj_init/PROMPT.md`，或 `uv run python src/backend/scripts/proj_init/main.py`。

whole-lca / revise-lca 前，用户须先手动 `src/backend/scripts/clean.py` 并复制资料（见根目录 `README.md`）。

## Worker 与模型

编排器固定使用 `--worker pi`。模型档案 id 来自 `.env` 的 `PI_MODEL`（见 `src/backend/config/model_profiles.json`）。

```bash
uv run python src/backend/scripts/workflow.py --workflow harness/LCA-main.yaml --worker pi
```

## MCP 与 Host Action

- **Agent MCP**（`registry.tools.mcp`）：注入 Pi 会话的 stdio MCP。
- **Host Action**（`registry.tools.host_action`）：Core 子进程 JSON stdin/stdout，由 stage `spec.yaml` 引用；不注入 Agent 工具列表。

## Agent 分层

| 层 | 位置 |
| --- | --- |
| 主编排 | `src/backend/core/workflow/` |
| 阶段与任务绑定 | `harness/LCA-*.yaml` |
| 机器契约 | `harness/specs/**/spec.yaml` |
| Worker 会话 | `src/backend/core/agents/` + `src/backend/pi-runtime/` |
| 业务 API | `src/backend/api/` |
| 前端 | `src/frontend/web/` |
| 环境引导 | `src/backend/scripts/proj_init/PROMPT.md` |
