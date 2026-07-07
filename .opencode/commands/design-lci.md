---
description: 调用 LCI-designer 智能体读取执行计划，并自动化构建符合 openLCA 规范的 LCI 数据及人类可读映射报告
agent: LCI-designer
---

**语言要求**：
目前，必须使用中文进行模型的思考、输出，调用 subagent 时也必须强调这一点。


**任务执行**：
你是 `LCI-designer`，请依次执行下列工作：

1. 在开始前，必须使用 uv 执行一次文件同步逻辑：`uv run python scripts/file_sync/main.py`；

2. 加载 `wf-lci-construction` 技能，将 `workspace/plan/execution_plan.md` 作为参考内容，按技能要求开展本次任务；

3. 再次使用 uv 执行一次文件同步逻辑：`uv run python scripts/file_sync/main.py`；

4. 任务结束后，立即终止当前会话

