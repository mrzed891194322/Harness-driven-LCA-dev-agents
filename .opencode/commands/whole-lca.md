---
description: 从已审核执行计划启动带审查、哈希预检、openLCA 自动导入读回和 LCIA 结果归档的无人值守端到端 LCA 工作流
agent: major-orchestrator
---

**任务执行**：

1. 在开始前，使用 uv 执行一次单向文件同步，将 `uploads/` 内容写入 `workspace/` 与 `harness/`：`uv run python scripts/file_sync/main.py --direction upload-to-work`；
2. 加载 `workflow-main`，将同步后的 `workspace/plan/execution_plan.md` 作为唯一计划输入，并按该 skill 与其引用的共享 spec 执行；
3. skill 返回后，再次使用 uv 执行反向单向文件同步，将 `workspace/` 与 `harness/` 的产物写回 `uploads/`：`uv run python scripts/file_sync/main.py --direction work-to-upload`；
4. 同步完成后立即结束当前会话。
