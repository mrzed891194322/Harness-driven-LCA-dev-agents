# Agent 角色职责

本目录是各平台 LCA 编排角色的**语义唯一来源**。阶段顺序、门禁与产物 schema 仍以 `harness/workflows/` 与 `harness/specs/` 为准。

| 角色 | 文件 | 平台 adapter |
| --- | --- | --- |
| 主编排 | `major-orchestrator.md` | `.codex/agents/`、`.opencode/agents/`、`.claude/agents/`、`.dsh/agent-presets/lca/`（顶层会话 persona）与 `.dsh/skills/{whole-lca,revise-lca}`（角色声明与委派约定） |
| 执行子 agent | `sub-executor.md` | 同左（DSH 无命名子 agent：主编排在 `subagent` 工具委派 prompt 中指明角色，并要求子 agent 先完整读取本文件） |
| 只读审查 | `eval-reviewer.md` | 同左 |

改角色边界：先改本目录，再同步各平台 adapter 的启动指令与权限配置（DSH 侧同步 `.dsh/agent-presets/lca/agent.cordis.yml` persona 与 `.dsh/skills/` 中的委派约定）。不要在 adapter 中复制完整角色正文。
