---
name: revise-lca
description: 从现有 LCA 最终报告、plan、LCI、运行 memory 和 workspace/inputs/revise.md 用户意见启动可追溯的完整修订，覆盖 plan 与最终报告并重新执行 openLCA/LCIA 门禁。适用于 revise-lca 或修改既有 LCA 结果。
---

# Revise-LCA 主工作流

将本技能作为 Codex 平台的 revise-lca 入口。修订专属契约位于
`harness/specs/08-lca-revise-pipeline/`，共享运行与 02–07 阶段契约位于
`harness/specs/public/` 和对应编号包；不要在 Agent 对话中重述或弱化。

## 启动

1. 运行 `uv run python src/scripts/file_sync/main.py --direction upload-to-work`。
2. 运行 `uv run python src/scripts/revise_lca/main.py snapshot --yes`；失败时停止，
   不得修改旧 workspace/openLCA。
3. 快照成功后运行
   `uv run python harness/tools/control_openlca/cleanup_output/main.py --yes`；
   失败时不得激活快照。
4. 清理成功后运行
   `uv run python src/scripts/revise_lca/main.py activate --yes`。
5. 如果当前活动 Agent 不是 `major-orchestrator`，只生成一个该 Agent，传递
   `platform=codex`、`workflow=revise-lca`、意见路径和执行
   `harness/pipelines/LCA-revise.md` 的要求；根线程不执行业务阶段。
6. `major-orchestrator` 完整读取并执行 `harness/pipelines/LCA-revise.md`。Codex
   中知识检索与 openLCA 规则均按 pipeline 条件加载。

## 无人值守中继

`major-orchestrator` 只可生成 `sub-executor` 和 `eval-reviewer`，等待其返回并按
pipeline 持久化证据。预检成功后在同一范围/hash 下立即继续导入，不请求额外确认。

## 强制完成

- baseline 始终只读；候选计划通过审查后才覆盖 `workspace/inputs/plan.md`。
- 最多三次 LCI 审查；范围/hash 变化、部分导入、断链、空结果或资源未释放均停止。
- 最终报告覆盖 `workspace/outputs/reports/lca_report.md` 并包含修订摘要、用户意见
  落实矩阵和基线差异。
- 返回后不执行反向文件同步，也不自动运行独立 LCA 质量评价。
