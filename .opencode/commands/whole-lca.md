---
description: 从已审核执行计划启动带审查、写入确认、openLCA 导入读回和 LCIA 结果归档的端到端 LCA 工作流
agent: major-orchestrator
---

**任务执行**：

1. 在开始前，使用 uv 执行一次文件同步：`uv run python scripts/file_sync/main.py`；
2. 加载 `workflow-main`，将同步后的 `workspace/plan/execution_plan.md` 作为唯一计划输入，并按该 skill 与其引用的共享 spec 执行；
3. skill 返回后，再次使用 uv 执行一次文件同步：`uv run python scripts/file_sync/main.py`；
4. 同步完成后立即结束当前会话。
