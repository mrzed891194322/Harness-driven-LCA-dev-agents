# harness/workflows（v5，三级：编排 → 节点 → agent）

- `orchestrations/<name>.yaml`：编排 = 节点有序列表（`full-lca`、`revise-lca`、`demo-*`）。`nodes:` 里可写节点名
  （`nodes/<名>.yaml`）或内联节点对象，可混写：`nodes: [lca-intake, {id: x, ...}]`。
- `nodes/<id>.yaml`：节点（requires、produces、inject、agents、flow、accept）。`agents:` 里可写 agent 模板名
  （`agents/<名>.yaml`，如 `executor: executor`）、内联 agent 对象（含 `prompt`、`deliver`），或
  `{agent: executor, tools: ..., max_turns: ...}` 引用模板并在本节点覆盖。produces 的 spec 缺省取执行者 `deliver.spec`。
- `agents/<名>.yaml`：agent 模板（prompt、access、deliver）。
- 规则正文在 `harness/rules/global|lca/`（节点 `inject:` 引用），交付物规格在 `harness/specs/`，技能和 MCP 都在 `harness/tools/`。
- 加载与校验：`src/backend/v5/config.py`；自检：`npm run doctor`。

## revise-lca

`revise_of: full-lca`, `plan_file: revise_plan.md`. A fresh run keeps every artifact untouched, keeps
`artifacts/plan/main_plan.md`, writes `revise_plan.md`, then runs 清单修订 → 映射修订 → 报告修订. Each node writes revision
files next to the originals: `<name>.rev<N>.<ext>` (`bom/bom.rev1.json`, `mapping/LCI.rev1/`, `report/raw.rev1/`), N = 1 +
the highest existing rev of that produce entry, saved in `runs/_run/revisions.json` (a resume reuses it). `requires`
resolve to the latest version (highest rev, else original). See `docs/refactor/v5/ARTIFACTS.md` and ISSUES I-45.
