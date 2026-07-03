---
description: 调用 plan-maker agent 对已生成的 LCA 执行计划与待完善清单进行修改与迭代
agent: plan-maker
---

**语言要求**：
目前，必须使用中文进行模型的思考、输出，调用 subagent 时也必须强调这一点。

**规范要求**：
当前 agent 必须加载 `project-regulation`；如涉及命令运行、文件操作或子 Agent 调用，必须按 `harness/rules/` 路由读取最小必要规则。任何 Python 命令必须使用 `uv run python ...`。

**任务执行**：
你是 `plan-maker`，请开展本次修改/迭代任务，并且必须将以下文件作为参考内容：
1. 已生成的 LCA 执行计划：`workspace/plan/execution_plan.md`
2. 用户提出修改后的待完善清单：`workspace/plan/todo_list.md`

按 `lca-specification` 揭示的计划修改读取顺序读取 harness 规范、模板与自检文件；如需写入文件，只能调用 `subagents/tools/doc-handler`。你需要依据已解决的清单项或反馈意见，在现有的 `workspace/plan/execution_plan.md` 和 `workspace/plan/todo_list.md` 上进行增量修正，并迭代更新文件内容。

**任务结束**：
待 `plan-maker` 完成计划修改和文件更新后，你只需向用户简单汇报结果即可，并立即终止当前会话。
