# harness/workflows（v5，三级：编排 → 节点 → agent）

- `orchestrations/<name>.yaml`：编排 = 节点有序列表（`full-lca`、`revise-lca`、`demo-*`）。`nodes:` 里可写节点名
  （`nodes/<名>.yaml`）或内联节点对象，可混写：`nodes: [lca-bom, {id: x, ...}]`。
- `nodes/<id>.yaml`：节点（requires、produces、inject、agents、flow、accept）。`agents:` 里可写 agent 模板名
  （`agents/<名>.yaml`，如 `executor: executor`）、内联 agent 对象（含 `prompt`、`deliver`），或
  `{agent: executor, tools: ..., max_turns: ...}` 引用模板并在本节点覆盖。produces 的 spec 缺省取执行者 `deliver.spec`。
- `agents/<名>.yaml`：agent 模板（prompt、access、deliver）。
- 规则正文在 `harness/rules/global|lca/`（节点 `inject:` 引用），交付物规格在 `harness/specs/`，技能和 MCP 都在 `harness/tools/`。
- 测评用 orch/node/spec 在 `.benchmark/harness/`（同构）；短名加载先搜该树再搜本目录，也可写相对仓库根的路径。见 `.benchmark/harness/README.md`。
- 加载与校验：`src/backend/workflow/config.py`；自检：`npm run doctor`。

## 流转（docs/architecture/WORKFLOW_DESIGN.md）

- 外层是 Python 队列（`queue.json`），节点按编排顺序执行；节点内是 LangGraph（执行者 → 审查者 → 交卷）。
- 交卷状态（submit MCP）：执行者 `ready` / `blocked`；审查者 `pass` / `revise` / `redo`（`redo` 需写目标节点和理由）。
  未交卷时节点结果记为 `no_submit`，`status.json`/`node_end` 的 `reason` 给出原因码（max_turns、timeout 等）。
- `flow:` 可省略（缺省：执行者 → 审查者，审查 `revise` 退回执行者）。边写 `from`/`to`，可选 `when`（交卷状态）；
  回边必须写 `max`；同一 `from` 不能混用有条件和无条件边。错误信息带 `file:line`。
- `redo`：审查者要求重做更早的节点（spec `may_redo` 列了目标时只能选其中的）。重做段插在请求节点之后，
  每次重做开新会话；`max_redos` 按运行计数，缺省 2；超出时拒绝（事件 `redo_refused`）。
- `max_check_retries` 缺省 3。节点级续跑：从第一个未通过的节点及其后续重新入队。

## revise-lca

普通编排，`start_rev: next`：节点以 `rev = 已有最大 rev + 1` 起跑（rev 由宿主设置，不能在 YAML 里写）。`plan_file: revise_plan.md`。
保留原产物和 `artifacts/plan/main_plan.md`，写 `revise_plan.md`，然后 清单修订 → 映射修订 → 报告修订。修订文件写在原文件旁：
`<name>.rev<N>.<ext>`（`bom/bom.rev1.json`、`mapping/LCI.rev1/`、`report/raw.rev1/`），rev 记在运行 manifest 里（键 `<node>@rev<N>`）。
`requires` 取最新版本。新开一次 revise 会清掉上一次未通过节点的 rev。
