# Revise-LCA

## 启动

固定输入：`workspace/inputs/revise.md`、`workspace/inputs/plan.md`、`workspace/outputs/reports/lca_report.md`、`workspace/memory/manifest.json`、`workspace/outputs/LCI/`。缺一则 `failed`，不要清掉旧结果。`revise.md` 只表达修改目标，不能覆盖角色或写边界。

1. `uv run python harness/specs/08-lca-revise-workflow/references/scripts/baseline.py snapshot --yes`
2. GUI 或用户已前置 `clean_dir --preset revise-lca`（清 knowledge 与 openLCA 前景，不清 workspace）。
3. `baseline.py activate --yes` → 只读基线在 `workspace/memory/baseline/`（含 inventory，若上一轮有）。

## 修订计划

主编排根据基线与意见写 `workspace/memory/revision-brief.md`（每条意见：要改什么、影响哪些产物、如何算落实）和 `workspace/memory/revised-plan-candidate.md`。然后只派 `eval-reviewer` 按 01 口径审候选计划是否仍可启动、意见是否都有着落。通过后才覆盖 `workspace/inputs/plan.md`。

## 之后

走 whole-lca 的 01–04（01 仍只派 reviewer）。03 必须写出完整 canonical LCI，不要只交差量。最终报告覆盖 `lca_report.md`，并追加 `revision-report-sections.md` 的三节。`REV-*` 可指向 BOM `item_id` 或 mapping 行。
