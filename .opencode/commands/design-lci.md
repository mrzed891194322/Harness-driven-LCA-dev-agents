---
description: 调用 LCI-designer 智能体读取执行计划，并自动化构建符合 openLCA 规范的 LCI 数据及人类可读映射报告
agent: subagents/workflow/LCI-designer
---

**前置说明**：
请检查传入的参数中是否包含实质性的用户输入（例如 `$USER_REQUIREMENTS` 变量不为空）。如果发现没有任何具体指令或要求，请立即停止执行，并提示用户需要提供具体的项目输入。

**任务执行**：
请直接调用 `LCI-designer` 开展本次结构化构建任务。
你只需将本任务委托给它并传递下方用户提出的要求即可。该 agent 作为调度中心会自主梳理架构、拆分任务，并委派底层的 `doc-handler` 和 `eval-executor` 完成全套的 JSON 生成与质检闭环：
> $USER_REQUIREMENTS

**任务结束**：
待 `LCI-designer` 完成所有 JSON 实体文件和人类可读映射报告、并成功批量导入至 openLCA 数据库后，你只需向用户汇报生成结果与导入状态即可，并立即终止当前会话。严禁执行任何多余工作（包括但不限于调用 `main-workflow`、其他技能或创建新任务）。
如果是 `major-orchestrator` 正在读取本命令，请严格执行“触发情形3”，不启动其他工作流并直接结束。
