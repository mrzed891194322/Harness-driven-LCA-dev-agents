---
description: 从现有 LCA 报告、运行证据和用户意见启动可追溯的完整修订与重算
---

**任务执行**：

- GUI/CLI 已在启动前通过 `src/scripts/clean_dir/main.py -y --preset revise-lca` 清理 knowledge 与 openLCA（不清理 workspace）；**不要**在 agent 内调用 `clean_dir` 或 MCP `cleanup_output`。
- 完整读取并执行 `harness/workflows/LCA-revise.md`，固定意见输入为 `workspace/inputs/revise.md`；用户参考资料只从 `harness/knowledge/` 读取。
- 返回后保留当前 `workspace/memory/`、`workspace/outputs/LCI/` 和 `workspace/outputs/reports/`，立即结束会话。
