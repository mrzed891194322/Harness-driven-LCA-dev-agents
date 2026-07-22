---
name: workflow-main
description: 从既有 execution_plan.md 执行带计划门禁、证据检索、三轮 LCI 审查、openLCA 写入预检与用户确认、导入读回、LCIA 计算和结果归档的 whole-lca 工作流时使用。
---

# Whole-LCA 主工作流

本 skill 是 OpenCode 平台适配层。共享状态机和产物契约只存在于 `harness/specs/workflow-run/`；不要在本文件中重定义 schema。

## 启动

1. 确认当前 Agent 是 `major-orchestrator`，计划路径是 `workspace/plan/execution_plan.md`。
2. 读取 `harness/specs/workflow-run/README.md`，再完整读取其列出的计划接收、运行状态和结果规范；在写相应文件前读取对应 JSON schema 或报告模板。
3. 生成符合规范的 `run_id`，创建日志/结果目录与 manifest。平台写为 `opencode`，主 Agent 写为 `major-orchestrator`。

## 执行状态机

严格按 `workflow_run_spec.md` 推进：

1. 调用 `subagents/workflow/eval-reviewer` 做计划接收审查；阻断时持久化结果并停止。
2. 从已通过计划提取所有 `GAP-*` 与背景映射任务，调用 `subagents/workflow/sub-executor` 完成 RAG 原文回读和 openLCA 候选查询。
3. 调用 `subagents/workflow/sub-executor` 生成 `workspace/LCI/`。
4. 调用 `subagents/workflow/eval-reviewer` 审查 LCI。attempt 1/2 未通过时，只把 issue ID 与受影响产物交给 `sub-executor` 定向修正；attempt 3 未通过时置为 `needs_review`，不得继续。
5. LCI 通过后让 `sub-executor` 调用 `preflight_import_lci`。保存返回值，把 manifest 置为 `awaiting_confirmation`，向用户展示活动数据库、目标分类、创建/更新/删除范围和 `preflight_hash`。
6. 只有用户对当前精确范围明确确认后，才把 `preflight_hash` 与 `user_confirmed=true` 交给同一专用执行 Agent；范围变化时回到预检并重新确认。
7. 依次完成导入、模型图读回、产品系统计算和结果报告，按 `lcia_results_spec.md` 验收后决定最终状态。

## 证据与停止

- 每次委派前后写 handoff，每个阶段写新 stage 文件；不得覆盖历史记录。
- Reviewer 只读；由主 Agent 持久化其返回的 review。
- 不调用任何既有 Agent，不访问或更新 `workspace/memory/`。
- 用户拒绝或未确认写入时保留 LCI，置为 `needs_review` 并返回 command 执行后置同步。
- 无部分失败、无断链、非空结果且全部契约通过前，不得标记 `completed`。
