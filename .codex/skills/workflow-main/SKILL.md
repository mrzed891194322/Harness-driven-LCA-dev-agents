---
name: workflow-main
description: 通过分阶段的计划接收、证据检索、最多三次 LCI 审查循环、openLCA 写入预检、自动导入回读、LCIA 计算及结果归档，来无人值守地执行已有的 LCA 执行计划（plan.md）。适用于本仓库中的 whole-lca 或端到端 plan-to-LCIA 运行。
---

# 全生命周期评价（Whole-LCA）主工作流

将此技能作为 Codex 平台适配器使用。运行契约、阶段规则与结果结构以 `harness/specs/public/` 与 `harness/specs/01-*` 至 `07-*` 为准；编排步骤以 `harness/workflows/LCA-main.md` 为唯一来源。不得在本 skill 中重述或弱化 workflow 内容。

## 启动

1. 在读取计划之前，运行 `uv run python src/scripts/file_sync/main.py --direction upload-to-work`，将参考资料同步到 harness 知识源。当环境需要时，可使用可写的临时 uv 缓存。
2. 仅使用 `workspace/inputs/plan.md` 作为计划输入。如果当前活动 Agent 不是 `major-orchestrator`，只生成一个该 Agent，并传递 `platform=codex`、计划路径及执行 `harness/workflows/LCA-main.md` 的要求；根线程不执行业务阶段。
3. `major-orchestrator` 完整读取并执行 `harness/workflows/LCA-main.md`。

## Codex 运行时补充

- 知识检索与 openLCA 规则在 Codex 中均不全局加载；按 workflow 条件读取 `harness/rules/knowledge-retrieval/README.md` 与 `harness/rules/openlca-operation/README.md`。
- `major-orchestrator` 仅可生成 `sub-executor` 和 `eval-reviewer`，等待其返回并按 workflow 持久化证据。
- 如果返回 `needs_input`、`needs_review` 或 `failed`，保留已记录状态并报告确切问题。
- 运行启动即授权在当前预检范围完全一致时执行导入；预检通过后立即继续第 06 阶段，不得请求额外确认。
- 工作流产物保存在 `workspace/memory/`、`workspace/outputs/LCI/` 和 `workspace/outputs/reports/`；返回后不执行反向文件同步。

## 禁止

- 不得在本 skill 中复制七阶段步骤、阶段 spec 路径列表或 schema 加载顺序（均由 workflow 定义）。
