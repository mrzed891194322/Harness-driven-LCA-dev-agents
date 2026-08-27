# 平台适配核对清单

同一套 Whole-LCA 契约只在 `harness/`。各平台保留自己的 agent、MCP 接线和 CLI command/skill；MCP **实现**只能在 `harness/tools/`。

## 一行 CLI（正式入口）

在仓库根目录执行。GUI 按 `.env` 的 `HARNESS_AGENT` 调用同一套 whole-lca / revise-lca 一行 CLI（四平台：OpenCode、Codex、Claude Code、DSH）。bootstrap-env 不在 GUI 内执行，仅在终端按各平台 adapter 自行运行。

| 平台 | Whole-LCA | Revise-LCA |
| --- | --- | --- |
| OpenCode | `opencode run --command whole-lca` | `opencode run --command revise-lca` |
| Codex | `codex exec -s workspace-write '$whole-lca'` | `codex exec -s workspace-write '$revise-lca'` |
| Claude Code | `claude --agent major-orchestrator -p "/whole-lca" --permission-mode dontAsk` | `claude --agent major-orchestrator -p "/revise-lca" --permission-mode dontAsk` |
| DSH | `DSH_PERMISSION_MODE=danger-full-access dsh --profile headless --patch .dsh/cordis.patch.yml "读取并执行 .dsh/skills/whole-lca/SKILL.md"` | `DSH_PERMISSION_MODE=danger-full-access dsh --profile headless --patch .dsh/cordis.patch.yml "读取并执行 .dsh/skills/revise-lca/SKILL.md"` |

不要把 IDE 对话当成启动器。交互会话里的 `/whole-lca`、`$whole-lca` 与上表是同一 command。

## MCP 接线（实现不复制）

各平台 config 当前只注册：

- `harness/tools/control_openlca/main.py`

`harness/tools/query_rag/main.py` 实现保留，但**不**写入 `.opencode/`、`.codex/`、`.claude/`、`.dsh/` 或 `.mcp.json`。推荐启动方式：`uv run python harness/tools/<server>/main.py`。

| 平台 | 配置位置 |
| --- | --- |
| OpenCode | `.opencode/opencode.json` → `mcp.*.command` |
| Codex | `.codex/config.toml` → `mcp_servers.*.command` / `args` |
| Claude Code | `.claude/settings.json` 与 `.mcp.json` → `mcpServers` |
| DSH | `.dsh/cordis.patch.yml` → `insert` 行 `@deepseek-ai/dsh-mcp-client`（`serverName: control_openlca`） |

禁止：

- 在 `.opencode/`、`.codex/`、`.claude/`、`.dsh/` 再实现一套 control_openlca / query_rag
- 新增 `harness/tools/mcp.json` 当平台只能翻译的总目录
- 把 `harness/workflows/` 七阶段正文复制进 agent
- 把未接入工作流的 `query_rag` 重新写进 agent config（除非后续初始化流程明确注册）
- 在 `~/.dsh/` 写仓库配置（DSH 项目配置只在 `.dsh/`，经 `--patch` 挂载）

## Agent / command 分层

| 层 | OpenCode | Codex | Claude Code | DSH |
| --- | --- | --- | --- | --- |
| MCP / 默认 agent | `.opencode/opencode.json` | `.codex/config.toml` | `.claude/settings.json` | `.dsh/cordis.patch.yml` |
| 角色语义（唯一来源） | `harness/roles/*.md` | 同左 | 同左 | 同左 |
| 平台 adapter（权限/沙箱/启动） | `.opencode/agents/*.md` | `.codex/agents/*.toml` | `.claude/agents/*.md` | `.dsh/agent-presets/lca/`（顶层会话 persona）；无命名子 agent，子 agent 角色由委派 prompt 指定并要求先读 `harness/roles/*.md` |
| CLI 拉起 | `.opencode/commands/*.md` | `.codex/skills/whole-lca`、`revise-lca` | `.claude/commands/*.md` | `.dsh/skills/whole-lca`、`revise-lca`、`bootstrap-env` |
| 业务步骤 | `harness/workflows/LCA-*.md` | 同左 | 同左 | 同左 |

OpenCode 环境引导使用内置 `build` agent（`opencode run --command bootstrap-env` → `agent: build`），不注册自定义 env-bootstrap。

不要在 Codex、DSH 配置或角色文档中硬编码模型名称；子 agent 模型由主编排在委派时按任务复杂度动态选择。

不要在 Codex 或 DSH 里放代码维护、harness 改进或独立质量评价 skill。DSH 无人值守用 `DSH_PERMISSION_MODE=danger-full-access`（默认 `workspace-write` 沙箱会把 `~/.cache` 只读挂载导致 `uv run` 失败，且 `ask` 审批无交互时 fail-closed）。
