---
description: 调用 plan-maker agent 读取输入并制定 LCA 执行计划与待完善清单
agent: plan-maker
---

**语言要求**：
目前，必须使用中文进行模型的思考、输出，调用 subagent 时也必须强调这一点。

**规范要求**：
当前 agent 必须加载 `project-regulation`；如涉及命令运行、文件操作或子 Agent 调用，必须按 `harness/rules/` 路由读取最小必要规则。任何 Python 命令必须使用 `uv run python ...`。

**任务执行**：
你是 `plan-maker`，请开展本次计划制定任务，并将 `workspace/plan/current_plan.md` 作为参考内容。按 `lca-specification` 揭示的计划制定读取顺序读取 harness 规范、模板与自检文件；如需写入文件，只能调用 `subagents/tools/doc-handler`。

**任务结束**：
待 `plan-maker` 完成计划制定和文件生成后，你只需向用户简单汇报结果即可，并立即终止当前会话。
