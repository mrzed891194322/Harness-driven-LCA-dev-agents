---
description: 调用 LCI-designer 智能体读取执行计划，并自动化构建符合 openLCA 规范的 LCI 数据及人类可读映射报告
agent: LCI-designer
---

**语言要求**：
目前，必须使用中文进行模型的思考、输出，调用 subagent 时也必须强调这一点。


**规范要求**：
当前 agent 必须加载 `project-regulation`；如涉及命令运行、文件操作或子 Agent 调用，必须按 `harness/rules/` 路由读取最小必要规则。任何 Python 命令必须使用 `uv run python ...`。


**任务执行**：
在开始前，必须使用 uv 执行一次文件同步逻辑：`uv run python scripts/file_sync/main.py`。
你是 `LCI-designer`，请开展本次结构化构建任务，并将 `workspace\plan\execution_plan.md` 作为参考内容。按 `lca-specification` 揭示的 LCI 构建读取顺序读取 harness 规范、模板与自检文件；该 agent 作为调度中心自主梳理架构、拆分任务，并委派底层的 `doc-handler` 和 `eval-executor` 完成全套的 JSON 生成与质检闭环。
任务结束后，必须再次使用 uv 执行一次文件同步逻辑：`uv run python scripts/file_sync/main.py`。


**任务结束**：
待 `LCI-designer` 完成所有 JSON 实体文件和人类可读映射报告、并成功批量导入至 openLCA 数据库后，你只需向用户汇报生成结果与导入状态即可，并立即终止当前会话。
