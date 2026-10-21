# harness/workflows（v5）

- `<name>.yaml`：一个工作流 = 节点 id 的有序列表（`demo-write`、`demo-swapped`、`demo-single`、`demo-missing-input`、`full-lca`）。
- `nodes/<id>.yaml`：节点（agents、flow、requires、produces）。produces 的 spec 缺省取执行者角色 `deliver.spec`。
- 角色、规则、交付物规格分别在 `harness/rules/roles/`、`harness/rules/global|lca/`、`harness/specs/`（YAML）。
- 加载与校验：`src/backend/v5/config.py`；自检：`npm run doctor`。

旧引擎的 `LCA-main.yaml` / `LCA-revise.yaml`、`.local/harness/workflows/` 副本同步、prompts/permissions 组件注册已删除（见 `docs/refactor/v5/COMMIT_PLAN.md` C7c）。

## revise-lca

`revise_of: full-lca`, `plan_file: revise_plan.md`. A fresh run keeps every artifact untouched, keeps
`artifacts/plan/main_plan.md`, writes `revise_plan.md`, then runs 清单修订 → 映射修订 → 报告修订. Each node writes revision
files next to the originals: `<name>.rev<N>.<ext>` (`bom/bom.rev1.json`, `mapping/LCI.rev1/`, `report/raw.rev1/`), N = 1 +
the highest existing rev of that produce entry, saved in `runs/_run/revisions.json` (a resume reuses it). `requires`
resolve to the latest version (highest rev, else original). See `docs/refactor/v5/ARTIFACTS.md` and ISSUES I-45.
