# 运行入口

同一套 Whole-LCA 契约只在 `harness/`。Python 主编排器是唯一运行入口。项目 MCP 由 `harness/LCA-main.yaml` 注册，经 `src/core/agents` 会话接口注入任务会话。当前实现 spawn PATH 上的 CLI；会话 DTO（spec / rule / 工具）与 CLI/SDK 无关。不再使用仓库内 `.codex/` / `.claude/` / `.dsh/` / `.opencode/` 平台 skill。

## 用户入口

```bash
uv run python src/gui/main.py
uv run python src/scripts/workflow.py --task whole-lca
uv run python src/scripts/workflow.py --task revise-lca
```

环境引导：读取并执行 `src/scripts/proj_init/PROMPT.md`，或 `uv run python src/scripts/proj_init/main.py`。

whole-lca / revise-lca 前，用户须先手动 `clean_dir` 并复制资料（见根目录 `README.md`），或走 GUI 的执行按钮（GUI 会做前置清理与同步）。

## GUI 启动用的一行 CLI

GUI 按 `.env` 的 `HARNESS_AGENT` 调用 Python 编排器并传入 `--worker`。模型 id 来自同文件的 `CODEX_MODEL` / `CLAUDE_MODEL` / `OPENCODE_MODEL` / `PI_MODEL`。

```bash
uv run python src/scripts/workflow.py --task whole-lca --worker <agent>
uv run python src/scripts/workflow.py --task revise-lca --worker <agent>
```

`agent` 为 `codex` / `claude` / `opencode` / `pi`。

## MCP 接线

项目 `control_openlca` 的唯一配置来源是主工作流 YAML 注册表，由 worker 会话在任务中注入。不要在仓库根目录再放一份 MCP 声明。

独立工具在 `harness/tools/control_openlca/main.py`；LCA YAML 使用 `src/domains/lca/openlca_mcp.py` 适配入口承接角色限制、审核批准与证据归档。普通外部 stdio MCP 只需注册 command/args/env 并绑定 assignment，不需要上下文协议；`tool_timeout_sec` 默认 60 秒，openLCA 显式为 7320 秒。其他 transport 当前会明确拒绝。

SDK 不导入具体工具代码；LCA capability 按需加载。

## Agent 分层

| 层 | 位置 |
| --- | --- |
| 主编排 | `src/core/orchestrator/` |
| 阶段与任务绑定 | `harness/LCA-*.yaml` |
| 契约与角色任务 | `harness/specs/` |
| Worker 会话 | `src/core/agents/`（当前 CLI provider；接口可换 SDK） |
| 环境引导 | `src/scripts/proj_init/PROMPT.md` |
