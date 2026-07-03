---
description: 调用 plan-maker agent 读取输入并制定 LCA 执行计划与待完善清单
agent: plan-maker
---

**语言要求**：
目前，必须使用中文进行模型的思考、输出，调用 subagent 时也必须强调这一点。

**规范要求**：
调用 `plan-maker` 时必须明确要求其加载 `project-regulation`；如涉及命令运行、文件操作或子 Agent 调用，必须按 `harness/rules/` 路由读取最小必要规则。任何 Python 命令必须使用 `uv run python ...`。

**任务执行**：
请直接调用 `plan-maker` 开展本次任务，调用时需说明将 `workspace/plan/current_plan.md` 作为参考内容。
你只需将本任务委托给它，并传递该参考内容以及下方用户提出的要求即可，该 agent 会自主依循其内置规范完成后续所有的计划梳理与文件写入工作。

**任务结束**：
待 `plan-maker` 完成计划制定和文件生成后，你只需向用户简单汇报结果即可，并立即终止当前会话。
