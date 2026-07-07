---
description: 调用 plan-maker agent 读取输入并制定 LCA 执行计划与待完善清单
agent: plan-maker
---

**语言要求**：
目前，必须使用中文进行模型的思考、输出，调用 subagent 时也必须强调这一点。


**任务执行**：
在开始前，必须使用 uv 执行一次文件同步逻辑：`uv run python scripts/file_sync/main.py`。

你是 `plan-maker`，请开展本次计划制定任务，并将 `workspace/plan/current_plan.md` 作为参考内容。按 `lca-specification` 揭示的计划制定读取顺序读取 harness 规范、模板与自检文件；如需写入文件，只能调用 `subagents/tools/doc-handler`。

任务结束后，必须再次使用 uv 执行一次文件同步逻辑：`uv run python scripts/file_sync/main.py`。

**任务结束**：
待 `plan-maker` 完成计划制定和文件生成后，你只需向用户简单汇报结果即可，并立即终止当前会话。
