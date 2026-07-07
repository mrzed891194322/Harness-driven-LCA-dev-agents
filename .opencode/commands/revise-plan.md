---
description: 调用 plan-maker 智能体对已生成的 LCA 执行计划与待完善清单进行修改与迭代
agent: plan-maker
---

**语言要求**：
目前，必须使用中文进行模型的思考、输出，调用 subagent 时也必须强调这一点。


**任务执行**：
你是 `plan-maker`，请依次执行下列工作：

1. 在开始前，必须使用 uv 执行一次文件同步逻辑：`uv run python scripts/file_sync/main.py`；

2. 加载 `wf-make-plan` 技能，将已生成的 LCA 执行计划（`workspace/plan/execution_plan.md`）与用户提出修改后的待完善清单（`workspace/plan/todo_list.md`）作为参考内容，按技能要求开展本次修改/迭代任务；

3. 再次使用 uv 执行一次文件同步逻辑：`uv run python scripts/file_sync/main.py`；

4. 任务结束后，立即终止当前会话
