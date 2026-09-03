---
id: 08-lca-revise-workflow
inputs:
  - workspace/inputs/revise.md
  - workspace/inputs/plan.md
  - workspace/outputs/reports/lca_report.md
  - workspace/memory/manifest.json
  - workspace/outputs/LCI/
outputs:
  - workspace/memory/revision-brief.md
  - workspace/memory/revised-plan-candidate.md
---

# 08 Revise-LCA 修订外壳

从既有结果与 `revise.md` 启动修订；之后复用 01–04。

快照脚本：`references/scripts/baseline.py`
报告增补：`references/templates/revision-report-sections.md`

## 输入

- `workspace/inputs/revise.md`
- `workspace/inputs/plan.md`
- `workspace/outputs/reports/lca_report.md`
- `workspace/memory/manifest.json`
- `workspace/outputs/LCI/`

缺一则未通过，不要清掉旧结果。

## 产物

- `workspace/memory/revision-brief.md`
- `workspace/memory/revised-plan-candidate.md`

审查通过后由主编排覆盖 `workspace/inputs/plan.md`。最终报告追加修订三节。

## 验收

每条意见在 brief 与候选计划中有着落；候选计划仍可按 01 口径启动。03 须完整重建 LCI。
