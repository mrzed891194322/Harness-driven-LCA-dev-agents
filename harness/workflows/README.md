# harness/workflows（v5）

- `<name>.yaml`：一个工作流 = 节点 id 的有序列表（`demo-write`、`demo-swapped`、`demo-single`、`demo-missing-input`、`full-lca`）。
- `nodes/<id>.yaml`：节点（agents、flow、requires、produces）。produces 的 spec 缺省取执行者角色 `deliver.spec`。
- 角色、规则、交付物规格分别在 `harness/rules/roles/`、`harness/rules/global|lca/`、`harness/specs/`（YAML）。
- 加载与校验：`src/backend/v5/config.py`；自检：`npm run doctor`。

旧引擎的 `LCA-main.yaml` / `LCA-revise.yaml`、`.local/harness/workflows/` 副本同步、prompts/permissions 组件注册已删除（见 `docs/refactor/v5/COMMIT_PLAN.md` C7c）。

## revise-lca

`revise_of: full-lca`, `plan_file: revise_plan.md`. A fresh run moves the last completed run's artifacts to
`artifacts/previous/` (read-only via `requires`), keeps `artifacts/plan/main_plan.md`, writes `revise_plan.md`, then runs
清单修订 → 映射修订 → 报告修订 into the normal `bom/`, `mapping/`, `report/` paths. See `docs/refactor/v5/ISSUES.md` I-16.
