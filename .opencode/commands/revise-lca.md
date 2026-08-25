---
description: 从现有 LCA 报告、运行证据和用户意见启动可追溯的完整修订与重算
agent: major-orchestrator
---

**任务执行**：

- 启动后**首先**按 `harness/workflows/LCA-revise.md` 的「运行前基线准备」完成 baseline 快照后的 MCP `health_check` 与 `cleanup_output`；**不要**在 agent 内清理 workspace。
- 完整读取并执行 `harness/workflows/LCA-revise.md`，固定意见输入为 `workspace/inputs/revise.md`；用户参考资料只从 `harness/knowledge/` 读取。
- 返回后保留当前 `workspace/memory/`、`workspace/outputs/LCI/` 和 `workspace/outputs/reports/`，立即结束会话。
