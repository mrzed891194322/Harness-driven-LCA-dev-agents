# 平台适配核对清单

同一套 Whole-LCA 契约只在 `harness/`。各平台只保留 MCP 接线；主编排是 Python 状态机。MCP **实现**只能在 `harness/tools/`。

## 用户入口

Cursor 不当操作员。开箱后在仓库根目录执行 `uv sync`（见根目录 `README.md`）。

whole-lca / revise-lca 前，用户须先手动 `clean_dir` 并复制资料（见根目录 `README.md`）。然后直接跑 Python 主编排：

```bash
uv run python src/scripts/lca_orchestrator/main.py --task whole-lca --worker opencode
uv run python src/scripts/lca_orchestrator/main.py --task revise-lca --worker dsh
```

`--worker` 为 `opencode` / `claude` / `codex` / `dsh` / `antigravity`。DSH worker 需要 `DSH_PERMISSION_MODE=danger-full-access`。不要在 IDE 里用 slash/skill 启动编排。

## GUI 启动用的一行 CLI

GUI 按 `.env` 的 `HARNESS_AGENT` 调用同一 Python 入口。这是 **GUI 内部启动方式**。

```bash
uv run python src/scripts/lca_orchestrator/main.py --task whole-lca --worker "$HARNESS_AGENT"
uv run python src/scripts/lca_orchestrator/main.py --task revise-lca --worker "$HARNESS_AGENT"
```

## MCP 接线（实现不复制）

各平台 config 当前只注册：

- `harness/tools/control_openlca/main.py`

推荐启动方式：`uv run python harness/tools/control_openlca/main.py`。

| 平台 | 配置位置 |
| --- | --- |
| OpenCode | `.opencode/opencode.json` → `mcp.*.command` |
| Codex | `.codex/config.toml` → `mcp_servers.*.command` / `args` |
| Claude Code | `.claude/settings.json` 与 `.mcp.json` → `mcpServers` |
| DSH | `.dsh/cordis.patch.yml` → `insert` 行 `@deepseek-ai/dsh-mcp-client`（`serverName: control_openlca`） |

禁止：

- 在 `.opencode/`、`.codex/`、`.claude/`、`.dsh/` 再实现一套 control_openlca
- 新增 `harness/tools/mcp.json` 当平台只能翻译的总目录
- 把 `harness/workflows/` 阶段循环复制进 agent
- 注册 named agent（`major-orchestrator` / `sub-executor` / `eval-reviewer`）
- 在 adapter 里放 whole-lca / revise-lca slash、skill 或 command（worker 会自动发现，可能嵌套编排）
- 在 `~/.dsh/` 写仓库配置（DSH 项目配置只在 `.dsh/`，经 `--patch` 挂载）

## Adapter 分层

| 层 | OpenCode | Codex | Claude Code | DSH |
| --- | --- | --- | --- | --- |
| MCP | `.opencode/opencode.json` | `.codex/config.toml` | `.claude/settings.json` | `.dsh/cordis.patch.yml` |
| 主编排 | `src/scripts/lca_orchestrator/` | 同左 | 同左 | 同左 |
| 阶段循环与提示词 | `harness/workflows/LCA-*.yaml` | 同左 | 同左 | 同左 |

不要在 Codex 或 DSH 配置中硬编码模型名称。不要在 Codex 或 DSH 里放代码维护 skill。DSH worker 用 `DSH_PERMISSION_MODE=danger-full-access`。
