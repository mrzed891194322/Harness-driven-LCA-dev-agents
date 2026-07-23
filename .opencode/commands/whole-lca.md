---
description: 从已审核执行计划启动带审查、哈希预检、openLCA 自动导入读回和 LCIA 结果归档的无人值守端到端 LCA 工作流
agent: major-orchestrator
---

**任务执行**：

1. 在开始前，使用 uv 将 `workspace/inputs/references/` 单向同步到 `harness/knowledge/inputs/user_ref/`：`uv run python src/scripts/file_sync/main.py --direction upload-to-work`；
2. 加载 `workflow-main`，将 `workspace/inputs/plan.md` 作为唯一计划输入，并按该 skill 与其引用的共享 spec 执行；
3. skill 返回后，保留 `workspace/memory/`、`workspace/outputs/LCI/` 和 `workspace/outputs/reports/` 中的固定产物并立即结束当前会话。
