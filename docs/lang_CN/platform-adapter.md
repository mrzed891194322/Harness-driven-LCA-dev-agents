# 运行入口

同一套 Whole-LCA 契约只在 `harness/`。用户侧**唯一**入口是 Web 控制面板；面板背后的 Python 编排器负责执行。项目 MCP 由 `harness/LCA-main.yaml` 注册，经 `src/backend/core/agents` 会话接口注入任务会话。Worker 为 **`src/backend/pi_client/`**（Python 客户端）+ **`src/pi-runtime/`**（Node Pi SDK 宿主），不再依赖 PATH 上的 `codex` / `claude` / `opencode` / `pi` 可执行文件。

## 用户入口

```bash
npm start         # 同步依赖后启动：FastAPI → 唯一的 pi-runtime → Next.js（见根目录 README）
npm run dev       # 不同步依赖，按同样顺序直接启动
npm run stop      # 停止全部（日常用它，不要靠 Ctrl-C）
npm run restart   # stop + start
```

浏览器访问控制面板后完成设置、计划、执行与结果查看。环境引导：读取并执行 `src/scripts/proj_init/PROMPT.md`，或 `uv run python src/scripts/proj_init/main.py`。

whole-lca / revise-lca 的预清理与资料准备在控制面板流程中完成（见根目录 `README.md`）。

## Worker 与模型

编排器固定使用 Pi SDK worker。模型档案 id 来自 `.env` 的 `PI_MODEL`（见 `src/backend/core/runtime/model_profiles.json`）。在 Web「设置」选择档案并配置 BYOK 凭证。

## MCP 与 Host Action

- **Agent MCP**（`registry.tools.mcp`）：注入 Pi 会话的 stdio MCP。
- **Host Action**（`registry.tools.host_action`）：Core 子进程 JSON stdin/stdout，由 stage `spec.yaml` 引用；不注入 Agent 工具列表。

## Agent 分层

| 层 | 位置 |
| --- | --- |
| 主编排 | `src/backend/core/workflow/` |
| 阶段与任务绑定 | `harness/LCA-*.yaml` |
| 机器契约 | `harness/specs/**/spec.yaml` |
| Worker 运行时 | `src/backend/pi_client/` + `src/pi-runtime/` |
| 业务 API | `src/backend/api/` + `src/backend/services/` |
| 前端 | `src/frontend/web/` |
| 环境引导 | `src/scripts/proj_init/PROMPT.md` |
