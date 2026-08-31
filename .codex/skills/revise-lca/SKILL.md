---
name: revise-lca
description: 从现有 LCA 最终报告、plan、LCI、运行 memory 和 workspace/inputs/revise.md 用户意见启动可追溯的完整修订，覆盖 plan 与最终报告并重新执行 openLCA/LCIA 门禁。适用于 revise-lca 或修改既有 LCA 结果。
---

# Revise-LCA 主工作流

将本技能作为 Codex 平台的 revise-lca 入口。修订专属契约位于
`harness/specs/08-lca-revise-workflow/`，01–04 编号包位于 `harness/specs/`；不要在 Agent 对话中重述或弱化。

## 启动

1. 当前 `codex exec` 会话即担任 `major-orchestrator`：先读取 `.codex/agents/major-orchestrator.toml` 的职责边界，再完整读取并执行 `harness/workflows/LCA-revise.md`。GUI 或用户已前置 `clean_dir --preset revise-lca` 并完成文件就位；**不要**在 agent 内调用 `clean_dir` 或 MCP `cleanup_output`。用户参考资料只从 `harness/knowledge/` 读取。不要再 spawn 另一个 `major-orchestrator`。只生成 `sub-executor` 和 `eval-reviewer`。每次委派前后在用户可见输出中写明当前阶段、被委派角色和等待原因；子 Agent 返回后立即摘要结论，不要用空的 Wait 心跳代替阶段进展。

## 无人值守中继

`major-orchestrator` 只可生成 `sub-executor` 和 `eval-reviewer`，等待其返回并按
workflow 持久化证据。规则由角色自读 `harness/rules/injection.md` 加载，不要在本 skill 或 workflow 中列出规则路径。
预检成功后在同一 import_scope 下立即继续导入，不请求额外确认。

## 强制完成

- baseline 始终只读；候选计划通过审查后才覆盖 `workspace/inputs/plan.md`。
- 最多三次阶段审查返工；库名/分类/LCI 目录变化、部分导入、断链、空结果或资源未释放均停止。
- 最终报告覆盖 `workspace/outputs/reports/lca_report.md` 并包含修订摘要、用户意见
  落实矩阵和基线差异。
- 返回后不自动运行独立 LCA 质量评价。
