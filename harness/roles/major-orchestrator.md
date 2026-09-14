# major-orchestrator

本文件仅作人读对照。whole-lca / revise-lca 的阶段推进由

`uv run python harness/workflows/lca_orchestrator/main.py`

执行。不要把当前 IDE 会话当成主编排去委派子 agent 或改写状态机。

主编排职责：写 `workspace/memory/manifest.json`、审查笔记与检查点，绑定 MCP 运行上下文，在写者提交后运行确定性检查，按 YAML 创建或续接 executor / reviewer 会话，决定 `completed` 或 `failed`，终止时写非空 `status_reason`。
