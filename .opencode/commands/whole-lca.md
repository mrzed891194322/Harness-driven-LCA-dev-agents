---
description: 从已审核执行计划启动带审查、范围预检、openLCA 自动导入读回和 LCIA 结果归档的无人值守端到端 LCA 工作流
agent: major-orchestrator
---

**任务执行**：

- 启动后**首先**按 `harness/workflows/LCA-main.md` 的「运行前 openLCA 清理」完成 MCP `health_check` 与 `cleanup_output`（先 `confirm=false` 预览，再 `confirm=true` 删除）；**不要**在 agent 内清理 workspace（GUI 已前置清理生成物）。
- 读取并执行 `harness/workflows/LCA-main.md` 定义的 LCA 完整工作流，将 `workspace/inputs/plan.md` 作为唯一计划输入；用户参考资料只从 `harness/knowledge/` 读取。
- 工作流返回后，保留 `workspace/memory/`、`workspace/outputs/LCI/` 和 `workspace/outputs/reports/` 中的固定产物并立即结束当前会话。
