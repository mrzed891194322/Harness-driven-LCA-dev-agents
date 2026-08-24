# 平台适配核对清单

同一套 Whole-LCA 契约只在 `harness/`。各平台保留自己的 agent、MCP 接线和 CLI command/skill；MCP **实现**只能在 `harness/tools/`。

## 一行 CLI（正式入口）

在仓库根目录执行。GUI 也调用同一套 OpenCode CLI。

| 平台 | Whole-LCA | Revise-LCA |
| --- | --- | --- |
| OpenCode | `opencode run --command whole-lca` | `opencode run --command revise-lca` |
| Codex | `codex exec -s workspace-write '$workflow-main'` | `codex exec -s workspace-write '$revise-lca'` |
| Claude Code | `claude --agent major-orchestrator -p "/whole-lca" --permission-mode dontAsk` | `claude --agent major-orchestrator -p "/revise-lca" --permission-mode dontAsk` |

不要把 IDE 对话当成启动器。交互会话里的 `/whole-lca`、`$workflow-main` 与上表是同一 command。

## MCP 接线（实现不复制）

各平台 config 的 command 必须包含：

- `harness/tools/query_rag/main.py`
- `harness/tools/control_openlca/main.py`

推荐启动方式：`uv run python harness/tools/<server>/main.py`。

| 平台 | 配置位置 |
| --- | --- |
| OpenCode | `.opencode/opencode.json` → `mcp.*.command` |
| Codex | `.codex/config.toml` → `mcp_servers.*.command` / `args` |
| Claude Code | `.claude/settings.json` 与 `.mcp.json` → `mcpServers` |

禁止：

- 在 `.opencode/`、`.codex/`、`.claude/` 再实现一套 query_rag / control_openlca
- 新增 `harness/tools/mcp.json` 当平台只能翻译的总目录
- 把 `harness/workflows/` 七阶段正文复制进 agent

## Agent / command 分层

| 层 | OpenCode | Codex | Claude Code |
| --- | --- | --- | --- |
| 模型/MCP/默认 agent | `.opencode/opencode.json` | `.codex/config.toml` | `.claude/settings.json` |
| 角色与权限 | `.opencode/agents/*.md` | `.codex/agents/*.toml` | `.claude/agents/*.md` |
| CLI 拉起 | `.opencode/commands/*.md` | `.codex/skills/workflow-main`、`revise-lca` | `.claude/commands/*.md` |
| 业务步骤 | `harness/workflows/LCA-*.md` | 同左 | 同左 |

质量评价 agent 与 improve skill 可以留在 `.codex/`；evaluator 不是跨平台公共包。
