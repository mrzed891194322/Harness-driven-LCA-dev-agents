---
description: 从现有 LCA 报告、运行证据和用户意见启动可追溯的完整修订与重算
agent: major-orchestrator
---

**任务执行**：

1. 运行 `uv run python src/scripts/revise_lca/main.py snapshot --yes`。失败时保留旧
   workspace/openLCA，记录缺失输入并停止。
2. 运行 `uv run python harness/tools/control_openlca/cleanup_output/main.py --yes`。
   失败时不得激活快照或清理旧 canonical 结果。
3. 只有清理成功后运行
   `uv run python src/scripts/revise_lca/main.py activate --yes`。
4. 完整读取并执行 `harness/workflows/LCA-revise.md`，固定意见输入为
   `workspace/inputs/revise.md`。
5. 返回后保留当前 `workspace/memory/`、`workspace/outputs/LCI/` 和
   `workspace/outputs/reports/`，立即结束会话。
