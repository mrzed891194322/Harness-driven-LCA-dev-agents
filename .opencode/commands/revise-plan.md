---
description: 调用 plan-maker agent 对已生成的 LCA 执行计划与待完善清单进行修改与迭代
agent: subagents/workflow/plan-maker
---

**语言要求**：
目前，必须使用中文进行模型的思考、输出，调用 subagent 时也必须强调这一点。

**任务执行**：
请直接调用 `plan-maker` 开展本次修改任务。调用时需明确指出这是一次修改/迭代任务，并且必须将以下文件作为参考内容：
1. 已生成的 LCA 执行计划：`src/plan/execution_plan.md`
2. 用户提出修改后的待完善清单：`src/plan/todo_list.md`

你只需将本修改任务委托给它，并传递上述参考文件内容以及下方用户提出的具体修改要求。该 agent 会依据已解决的清单项或反馈意见，在现有的 `src/plan/execution_plan.md` 和 `src/plan/todo_list.md` 上进行增量修正，并迭代更新文件内容。

**任务结束**：
待 `plan-maker` 完成计划修改和文件更新后，你只需向用户简单汇报结果即可，并立即终止当前会话。严禁执行任何多余工作（包括但不限于调用 `main-workflow`、其他技能或创建新任务）。
如果是 `major-orchestrator` 正在读取本命令，请严格执行“触发情形3”，不启动其他工作流并直接结束。
