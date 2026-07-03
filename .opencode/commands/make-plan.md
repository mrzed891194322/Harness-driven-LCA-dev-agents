---
description: 调用 plan-maker agent 读取输入并制定 LCA 执行计划与待完善清单
agent: subagents/workflow/plan-maker
---

**语言要求**：
目前，必须使用中文进行模型的思考、输出，调用 subagent 时也必须强调这一点。

**任务执行**：
请直接调用 `plan-maker` 开展本次任务，调用时需说明将 `workspace/plan/current_plan.md` 作为参考内容。
你只需将本任务委托给它，并传递该参考内容以及下方用户提出的要求即可，该 agent 会自主依循其内置规范完成后续所有的计划梳理与文件写入工作。

**任务结束**：
待 `plan-maker` 完成计划制定和文件生成后，你只需向用户简单汇报结果即可，并立即终止当前会话。严禁执行任何多余工作（包括但不限于调用 `main-workflow`、其他技能或创建新任务）。
如果是 `major-orchestrator` 正在读取本命令，请严格执行“触发情形3”，不启动其他工作流并直接结束。
