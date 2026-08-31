# LCA 修订主工作流

修订外壳在 `harness/specs/08-lca-revise-workflow/`；01–04 仍用编号包。不要在本文件加 schema。

## 运行前基线准备

1. `uv run python harness/specs/08-lca-revise-workflow/references/scripts/baseline.py snapshot --yes`
2. `baseline.py activate --yes`

`harness/knowledge/` 与 openLCA 前景须在启动前由 GUI 或用户用 `src/scripts/clean_dir/main.py -y --preset revise-lca` 清理（不清 workspace）。不要在 agent 内调 `clean_dir` 或 MCP `cleanup_output`。

## 渐进加载

1. 当前 Agent 是 `major-orchestrator`。意见输入为 `workspace/inputs/revise.md`；资料只从 `harness/knowledge/` 读。
2. 基线激活后只读取 `harness/specs/08-lca-revise-workflow/README.md`、`harness/specs/08-lca-revise-workflow/references/revise-lca-spec.md`、`harness/specs/public/README.md` 和 `harness/specs/public/references/workflow-runtime-spec.md`。不得预读编号阶段规范。
3. 每次委派列出当前阶段与允许读取的 baseline/当前路径。子 Agent 不得扫描其他阶段。不要在委派 prompt 中抄规则路径。
4. 进入 01–04 某阶段时才读取该阶段 README/spec。

## 修订计划

- 主 Agent 按 08 spec 写 `revision-brief.md` 与候选计划。
- 委派任务必须明确要求 `eval-reviewer` 读取 08 README/spec、01 门禁 README/spec，以及意见、baseline、brief、候选计划。
- 通过后覆盖 `workspace/inputs/plan.md`；未通过则 `failed` 并停止。

## 复用 01–04

覆盖计划后按 `harness/workflows/LCA-main.md` 的 01–04 执行（01 仍只派 reviewer）。03 必须完整重建 LCI。04 报告追加 `harness/specs/08-lca-revise-workflow/references/templates/revision-report-sections.md`。
