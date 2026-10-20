# pi-coding-agent 1.1.0 → 1.3.0 升级记录（2026-10-20）

依赖：`src/pi-runtime/package.json` 中的 `@earendil-works/pi-coding-agent` 从 1.1.0 升到 1.3.0（精确版本）。

## 本项目用到的 API
`createAgentSession`、`createMcpExtension`、`DefaultResourceLoader`、`ModelRuntime`、`SessionManager`、`SettingsManager`；session 上的 prompt / subscribe / abort / cancel / dispose / resume / getAllTools / getActiveToolNames / bindExtensions / extensionRunner / systemPrompt / model / thinkingLevel / sessionId / sessionFile。主要在 `src/pi-runtime/src/session_host.ts`、`auth_login.ts`。

## 1.2.0 / 1.3.0 的破坏性变更与本项目的关系
| 变更 | 影响 |
|---|---|
| `before_agent_start` 事件改为按 `messageType` 区分的联合类型；启动期间 session 视为忙 | 未使用 `before_agent_start` / `pi.sendMessage`，无影响 |
| 主题 / 配置 schema 地址迁移 | 未使用主题与 `$schema`，无影响 |
| `pi mcp list --json` 不再给出 resources 计数；连接 MCP 时不再列出 resources | 未调用；我们的 MCP 只提供 tools，无影响 |
| `kimi-coding` 改走 Chat Completions，`models.json` 中的 baseUrl 必须带 `/v1` | 未使用 `kimi-coding`（profile `opencode-go` 用的是 `opencode-go` provider）。若用户自定义 `base_url` 指向 kimi-coding，需要补上 `/v1` |
| OpenCode Go 改用 `opencode.ai/inference` 端点 | pi 内部处理，需要在真实运行中确认 `opencode-go` profile 仍然可用 |
| resume 会恢复 session 原有的活动工具 | 我们每个 turn 都显式设置工具；需要在真实运行中确认续跑行为 |

## 代码改动
无。`tsc` 零错误，51 个 pi-runtime 测试和 719 个 pytest 全部通过。

## 待验证
真实 GUI 运行一次完整 LCA，GWP 要与基线一致（Case1 223.67 / Case2 790.09 / Case3 787.93 / Case3-S 786.58）。
