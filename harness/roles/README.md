# Agent 角色职责

本目录是三平台 LCA 编排角色的**语义唯一来源**。阶段顺序、门禁与产物 schema 仍以 `harness/workflows/` 与 `harness/specs/` 为准。

| 角色 | 文件 | 平台 adapter |
| --- | --- | --- |
| 主编排 | `major-orchestrator.md` | `.codex/agents/`、`.opencode/agents/`、`.claude/agents/` |
| 执行子 agent | `sub-executor.md` | 同左 |
| 只读审查 | `eval-reviewer.md` | 同左 |

改角色边界：先改本目录，再同步各平台 adapter 的启动指令与权限配置。不要在 adapter 中复制完整角色正文。
