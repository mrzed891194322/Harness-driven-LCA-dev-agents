# Revise-LCA schema mapping

| 交接 | 唯一契约 | 主要产物 |
| --- | --- | --- |
| GUI/CLI → 修订接收 | `references/revise-lca-spec.md` | `workspace/inputs/revise.md` |
| 旧运行 → 基线 | `src/scripts/revise_lca/main.py` | `workspace/memory/baseline/` |
| 修订接收 → 计划审查 | `references/schemas/revision-brief.schema.json` | `revision-brief.json`、候选计划 |
| 主编排 → 运行状态 | `references/schemas/workflow-manifest.schema.json` | `workspace/memory/manifest.json` |
| 阶段 02–07 | 对应编号阶段包与 public schema | LCI、导入、模型图、raw、报告 |
| 报告覆盖 | 07 报告模板及 revision report sections | `lca_report.md` |
| 最终验收 | `references/scripts/validation.py` | baseline/brief/manifest/report 联合校验 |
