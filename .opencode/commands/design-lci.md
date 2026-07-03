---
description: 调用 LCI-designer 智能体读取执行计划，并自动化构建符合 openLCA 规范的 LCI 数据及人类可读映射报告
agent: LCI-designer
---

**语言要求**：
目前，必须使用中文进行模型的思考、输出，调用 subagent 时也必须强调这一点。


**规范要求**：
调用 `LCI-designer` 时必须明确要求其加载 `project-regulation`；如涉及命令运行、文件操作或子 Agent 调用，必须按 `harness/rules/` 路由读取最小必要规则。任何 Python 命令必须使用 `uv run python ...`。


**任务执行**：
请直接调用 `LCI-designer` 开展本次结构化构建任务，调用时需说明将 `workspace\plan\execution_plan.md` 作为参考内容。。
你只需将本任务委托给它并传递下方用户提出的要求即可。该 agent 作为调度中心会自主梳理架构、拆分任务，并委派底层的 `doc-handler` 和 `eval-executor` 完成全套的 JSON 生成与质检闭环：


**任务结束**：
待 `LCI-designer` 完成所有 JSON 实体文件和人类可读映射报告、并成功批量导入至 openLCA 数据库后，你只需向用户汇报生成结果与导入状态即可，并立即终止当前会话。
