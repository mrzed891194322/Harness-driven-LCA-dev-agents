---
description: 从已审核执行计划启动带审查、范围预检、openLCA 自动导入读回和 LCIA 结果归档的无人值守端到端 LCA 工作流
---

**任务执行**：

- GUI 或用户已在启动前通过 `src/scripts/clean_dir/main.py -y --preset whole-lca` 完成清理，并把资料放到 `harness/knowledge/`、计划写到 `workspace/inputs/plan.md`；**不要**在 agent 内调用 `clean_dir` 或 MCP `cleanup_output`。
- 读取并执行 `harness/workflows/LCA-main.md` 定义的 LCA 完整工作流，将 `workspace/inputs/plan.md` 作为唯一计划输入；用户参考资料只从 `harness/knowledge/` 读取。
- 工作流返回后，保留 `workspace/memory/`、`workspace/outputs/LCI/` 和 `workspace/outputs/reports/` 中的固定产物并立即结束当前会话。
