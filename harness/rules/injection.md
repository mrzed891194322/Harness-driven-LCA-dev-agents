# 规则注入清单

接到任务后：根据本角色与当前阶段加载下表路径。不要预读未列出的规则。路径相对仓库根。

主编排委派时只列阶段、角色、spec 与输入/产物路径，不要把本表抄进 prompt。

## 项目总则（所有角色、所有阶段）

- `harness/rules/project/write-boundary.md`
- `harness/rules/project/runtime.md`
- `harness/rules/project/paths.md`

## major-orchestrator

任意阶段：仅项目总则。不要加载 `harness/rules/lca/` 阶段文件或 `harness/rules/tools/`。

## eval-reviewer

| 阶段 | 额外规则 |
| --- | --- |
| `01-intake-gate` | `harness/rules/lca/method.md`、`harness/rules/lca/knowledge-files.md`、`harness/rules/lca/eval/01-intake.md` |
| `02-inventory-extraction` | `harness/rules/lca/method.md`、`harness/rules/lca/knowledge-files.md`、`harness/rules/lca/eval/02-inventory.md` |
| `03-dataset-mapping` | `harness/rules/lca/method.md`、`harness/rules/lca/knowledge-files.md`、`harness/rules/lca/eval/03-mapping.md`、`harness/rules/tools/control_openlca.md` |
| `04-openlca-reporting` | `harness/rules/lca/method.md`、`harness/rules/lca/knowledge-files.md`、`harness/rules/lca/eval/04-reporting.md`、`harness/rules/tools/control_openlca.md` |
| `08-lca-revise-workflow` | `harness/rules/lca/method.md`、`harness/rules/lca/knowledge-files.md`、`harness/rules/lca/eval/08-revise.md`、`harness/rules/lca/eval/01-intake.md` |

## sub-executor

本角色不承担 `01-intake-gate` 或修订计划审查。

| 阶段 | 额外规则 |
| --- | --- |
| `02-inventory-extraction` | `harness/rules/lca/method.md`、`harness/rules/lca/knowledge-files.md`、`harness/rules/lca/exec/02-inventory.md` |
| `03-dataset-mapping` | `harness/rules/lca/method.md`、`harness/rules/lca/knowledge-files.md`、`harness/rules/lca/exec/03-mapping.md`、`harness/rules/tools/control_openlca.md` |
| `04-openlca-reporting` | `harness/rules/lca/method.md`、`harness/rules/lca/knowledge-files.md`、`harness/rules/lca/exec/04-reporting.md`、`harness/rules/tools/control_openlca.md` |
