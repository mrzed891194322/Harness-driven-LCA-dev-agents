---
name: workflow-main
description: 通过分阶段的计划接收、证据检索、最多三次 LCI 审查循环、openLCA 写入预检与用户确认、导入回读、LCIA 计算及结果归档，来执行已有的 LCA 执行计划（execution_plan.md）。适用于本仓库中的 whole-lca 或端到端 plan-to-LCIA 运行。
---

# 全生命周期评价（Whole-LCA）主工作流

将此技能作为 Codex 平台适配器使用。将 `harness/specs/workflow-run/` 视为模式、状态转换、结果契约和报告结构的唯一来源；不要重述或弱化其中的内容。

## 启动运行

1. 在读取计划之前，先运行 `uv run python scripts/file_sync/main.py`。当环境需要时，可使用可写的临时 uv 缓存。
2. 仅使用从 `uploads/plan/execution_plan.md` 同步而来的 `workspace/plan/execution_plan.md`。
3. 完整阅读 `harness/specs/workflow-run/README.md`，然后依次完整阅读其 plan-intake、workflow-run 和结果引用。在生成对应产物之前，立即阅读相应的 JSON 模式或报告模板。
4. 如果当前活动的 Agent 不是 `major-orchestrator`，则仅生成一个 `major-orchestrator` 实例，并传递 `platform=codex`、计划路径以及指示其进入预检阶段的指令。不要在根线程中执行其业务阶段。

## 中继确认关卡

`major-orchestrator` 仅可生成 `sub-executor` 和 `eval-reviewer`。等待其返回结果。

- 如果返回 `needs_input`、`needs_review` 或 `failed`，则保留已记录的状态并报告确切问题。
- 如果返回 `awaiting_confirmation`，则向用户展示当前活动的数据库、目标类别、所有创建/更新/删除范围以及 `preflight_hash`。结束当前轮次并请求明确的确认；沉默或模糊的批准不视为确认。
- 在用户确认了该确切范围后，若同一编排器可用则恢复之，否则根据持久化的清单启动新的编排器，并传递不变的 `preflight_hash` 以及 `user_confirmed=true`。任何范围/哈希值的变更都需要重新进行预检和确认。

## 强制完成

- 将每个阶段/审查/交接都保存为新文件；不要覆盖历史记录，也不要使用 `workspace/memory/`。
- 在第三次 LCI 审查失败后停止，不再进行第四次自动修复。
- 要求达到以下条件后才能标记为 `completed`：零导入失败、无断裂的模型链接、非空的原始 LCIA 结果、已释放的计算资源，以及所有必需的结果产物。
- 在工作流返回后（包括受控停止）运行 `uv run python scripts/file_sync/main.py`，以确保可交付的 LCI 和计划文件已同步。
