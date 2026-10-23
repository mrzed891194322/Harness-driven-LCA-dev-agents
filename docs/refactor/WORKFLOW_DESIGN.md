# 工作流统一重建设计（外层队列 + 内层 LangGraph）

状态：设计稿，未改代码。破坏式重建：不兼容旧运行、旧 YAML、旧 submit 格式、旧事件。拓扑视图不在范围内。
依据的现状代码：`src/backend/workflow/runner.py`（356 行，手写 while 状态机）、`config.py`（`Flow/Edge/OUTCOMES`）、
`revisions.py`（revise-lca 的 `.rev<N>`）、`harness/tools/mcp/submit/main.py`（ok|stop / pass|reject|stop）、
`pi_driver.py`（`run_turn`、`submit_round_N.json`、`submit_rejections.jsonl`）、`events.py`、`progress_view.py`、
前端 `components/runs/{agent-stream,activity-summary}.tsx`。

## 0. 总体

- **外层**：普通 Python 线性队列，节点之间没有图。唯一的非线性是"经审核批准的回溯上游"（redo_upstream），做法是**往队尾追加**重做节点。
- **内层**：每个节点内部用 LangGraph `StateGraph` 跑 agent 编排（executor / reviewer …），图由节点 YAML 的 `agents` + `flow` 构建。
- 两层都只读**结构化提交**（submit 工具的参数，按 schema 校验），不解析自由文本。
- 同时并入简化 #1（结构化活动流）与 #2（SessionLaunchSpec 以 Python 为单一来源），见 §6、§9。

## 1. 外层：线性队列

```python
@dataclass
class QueueItem:
    node: str          # 节点 id
    rev: int           # 0 = 首次；1,2,… = 第几次重做
    reason: dict | None  # 重做来源：{requested_by, target, artifact, field, evidence, change}

queue = deque(QueueItem(n, 0, None) for n in workflow.nodes)
while queue:
    item = queue.popleft()
    outcome = run_node(item)          # 内层图，返回 NodeOutcome
    match outcome.kind:
        case "passed": continue
        case "redo_upstream": append_redo(queue, item, outcome.redo)
        case "blocked" | "failed": stop_run(outcome)
```

**追加规则**：节点 N 的重做请求获批（目标 T，T 在本次运行的有序节点列表中位于 N 之前，默认任意更早节点均可）后，
把 `T, T+1, …, N` 依次以 `rev = 该节点已有最大 rev + 1` 追加到队尾。例：`04` 请求重做 `03` → 追加 `03(rev1), 04(rev1)`。
字面"追加到队尾"会让排在 N 后面、尚未执行的节点（如 `05`）先跑并读到旧版本，所以本文定为：重做段**插在剩余队列最前面**，
紧接 N 之后执行，原后续节点顺延（`queue.extendleft(reversed(redo_items))`）。见 §12 问题 1。

> 示例：队列 `[01,02,03,04,05]`，跑完 04 时 04 请求重做 03 并获批 → 剩余队列 `[03r1, 04r1, 05]`。

**重做上限**：orchestration 字段 `max_redos`（整次运行的重做请求次数，默认 `2`，0 表示禁止回溯）。
超过时节点结果按 `failed` 处理，run 结束，`status_reason = "redo_limit: 已达 max_redos=<n>，<node> 请求重做 <target> 被拒"`，事件 `redo_refused{reason:"max_redos"}`。
目标非法（不存在、不在请求节点之前、是自身）同样失败，`reason: "redo_target_invalid"`。（submit 阶段先校验，见 §3，正常到不了这里。）

**rev 产物命名与目录**（替代 `revisions.py` 的 revise-lca 方案，统一成一套）：
- rev 0 写原路径：`artifacts/bom/bom.json`。
- rev k 写 `artifacts/bom/bom.rev<k>.json`；目录产物 `artifacts/mapping/LCI.rev<k>/`。旧版本全部保留。
- 节点运行目录：`runs/<node>/` → `runs/<node>@rev<k>/`（k=0 时仍是 `runs/<node>/`），里面是 `<agent>/attempt_<n>/submit.json` 等。
- **下游读最新版**：宿主在节点开始时解析 `requires`：每个路径取已存在的最高 rev（`revisions.latest` 保留，去掉 `below`/allocate/save 逻辑），
  解析结果写进 prompt 的 `<inputs>` 并记事件 `node_paths`。agent 永远看到具体路径，不自己找最新版。
- revise-lca 成为普通 orchestration：它的节点以 `rev = 已有最大 rev + 1` 起跑（orchestration 字段 `start_rev: next`），不再需要 `revise_of`、`revisions.json`。

**续跑（保留，节点级）**：`runs/_run/queue.json` 在每个节点结束时落盘（已完成项 + 剩余队列 + redo 计数）。续跑 = 读它，从第一个未完成项开始，清掉该项的 `runs/<node>@rev<k>/` 和它的 rev k 产物后重跑。节点内部不续跑（没有 checkpointer）。

## 2. 内层：LangGraph StateGraph

**依赖**：`langgraph`（仅 `StateGraph`、`RetryPolicy`），不用 checkpointer、不用 interrupt。
启动时显式关闭 LangSmith：进程入口设置 `os.environ["LANGCHAIN_TRACING_V2"]="false"`、`LANGSMITH_TRACING="false"`，并删除 `LANGCHAIN_API_KEY`/`LANGSMITH_API_KEY` 环境变量的继承；doctor 检查这一点。
后端进程崩溃后的恢复不在范围内（重启后按 §1 节点级续跑）。

**状态**：
```python
class NodeState(TypedDict):
    node: str; rev: int
    step: int                      # 已执行的 agent 轮数（全节点计数）
    attempts: dict[str, int]       # 每个 agent 的轮数
    last: dict[str, dict]          # agent -> 最近一次结构化提交（已过 schema）
    history: Annotated[list[dict], operator.add]  # 所有提交，按序
    feedback: str | None           # 下一轮要给 executor 的返工意见
    outcome: dict | None           # 终态：{kind, reason, redo}
```

**构建**：每个 `agents` 键一个图节点，函数体 = 组 prompt → 调现有 `driver.run_turn(TurnRequest)` → 读 submit → 写入 state。
`flow` 描述边：
- `start`: 起始 agent。
- `edges`: 无条件边 `{from, to}`。
- 条件边 `{from, when: <verdict|status>, to}`；`when` 只能是该 agent 提交 schema 里的枚举值（见 §3），路由函数只读 `state["last"][from]["status"|"verdict"]`。
- `join`: `{from: [a, b], to: c}`（并行 agent 汇合，LangGraph 原生 fan-in；当前 LCA 节点用不到，保留语法）。
- 回边（指向已执行过的节点）必须带 `max: <n>`，超过则走 `on_exhausted` 目标（默认 `failed`，原因 `back_edge_limit`）。
- `max_steps`（默认 12）：全节点 agent 轮数上限，超过 → `failed: max_steps`（作为 LangGraph `recursion_limit` 之外的显式检查）。
- 终点：`done`、`failed`、`blocked`、`redo_upstream`，映射为图的 `END` 并在 state.outcome 里记种类。
**重试**：仅对"传输/模型错误"（`TurnResult.error` 且非 fatal、无 submit）用 `RetryPolicy(max_attempts=2, retry_on=TransientTurnError)`；没有提交、鉴权失败等不重试。
**YAML 错误**：沿用 `config.py` 的 `ConfigError` + `_line_of`，所有错误带 `file:line`：未知 agent、条件值不在枚举、回边缺 `max`、终点不可达、`when` 与无条件边混用同一 from 等。

## 3. 提交（submit）状态与 schema

submit MCP 按 agent 类型暴露不同参数；宿主（不是 MCP）用同一份 JSON Schema 再校验一次。

**executor**
```json
{"oneOf": [
 {"properties": {"status": {"const": "done"}, "summary": {"type":"string","minLength":1},
   "artifacts": {"type":"array","minItems":1,"items":{"type":"string"}}},
  "required": ["status","summary","artifacts"], "additionalProperties": false},
 {"properties": {"status": {"const": "blocked"}, "reason": {"type":"string","minLength":20}},
  "required": ["status","reason"], "additionalProperties": false},
 {"properties": {"status": {"const": "redo_upstream"},
   "target_node": {"type":"string"}, "artifact": {"type":"string"}, "field": {"type":"string"},
   "evidence": {"type":"string","minLength":20}, "requested_change": {"type":"string","minLength":10}},
  "required": ["status","target_node","artifact","field","evidence","requested_change"], "additionalProperties": false}
]}
```
- `done`：MCP 仍检查交付物存在且符合 spec schema（现 `_check_produces`），`artifacts` 必须覆盖节点全部 produces。
- `redo_upstream`：MCP 校验 `target_node` 在本运行中位于当前节点之前、`artifact` 是该节点的 produces 之一。

**reviewer**
```json
{"oneOf": [
 {"properties": {"verdict": {"const":"approve"}, "summary": {"type":"string"}}, "required":["verdict"], "additionalProperties": false},
 {"properties": {"verdict": {"const":"reject"}, "issues": {"type":"array","minItems":1,
   "items":{"type":"object","required":["where","problem","expected"],"properties":{"where":{"type":"string"},"problem":{"type":"string"},"expected":{"type":"string"}}}}},
  "required":["verdict","issues"], "additionalProperties": false},
 {"properties": {"verdict": {"const":"approve_redo_upstream"}, "comment": {"type":"string"}}, "required":["verdict"], "additionalProperties": false},
 {"properties": {"verdict": {"const":"terminate"}, "reason": {"type":"string","minLength":20}}, "required":["verdict","reason"], "additionalProperties": false}
]}
```
`approve_redo_upstream` 只在 executor 最近一次提交为 `redo_upstream` 时可用（MCP 读 state 文件判断），否则拒收；
executor 提交 `done` 时 reviewer 只能 `approve | reject | terminate`。

**回合结束未提交** = 错误：节点 `failed`，`reason: "no_submit"`（细分 `max_turns | timeout | too_many_rejections | aborted`，沿用 pi_driver 的 abort_reason）。

**到节点结果的映射**

| executor | reviewer | 图走向 | 节点结果 |
|---|---|---|---|
| done（宿主检查不过） | — | 回 executor（回边计数） | — |
| done | approve | done | passed |
| done | reject | 回 executor，issues 作为 `<rework>` | —（超回边 max → failed: back_edge_limit） |
| done | terminate | failed | failed（run 停） |
| blocked | — | blocked（不经 reviewer） | blocked（run 停，status_reason=reason） |
| redo_upstream | approve_redo_upstream | redo_upstream | redo_upstream → 外层追加 |
| redo_upstream | reject | 回 executor（意见：自己修） | — |
| redo_upstream | terminate | failed | failed |
| 无提交 / fatal | — | failed | failed |

无 reviewer 的节点：`done → passed`，`redo_upstream` 直接视为未批准 → 节点 failed（`redo_needs_reviewer`）。

## 4. 回溯判据写在 spec 里

每个 spec 增加 `upstream` 段；宿主据此生成 prompt 的 `<redo_policy>`，executor 和 reviewer 都看到。

```yaml
# harness/specs/lca-mapping.yaml
upstream:
  may_redo: [lca-bom]            # 允许回溯的目标（省略 = 任意更早节点）
  criteria:
    - BOM 行的数量或单位与原始资料矛盾，且本节点无法从资料重新确定
    - BOM 缺少计划要求的情景，导致映射无对象可映射
  not_upstream:
    - 背景数据集选择、地域代理、单位换算——本节点自行处理
```
生成的 prompt 固定加一句：「凡是你自己能在本节点修正的问题，不得报告 blocked，也不得请求回溯上游；只有满足上面判据时才用 redo_upstream，并给出证据。」reviewer 的提示同理："不满足判据的回溯请求一律 reject。"

## 5. YAML 示例（三层）

```yaml
# harness/workflows/orchestrations/full-lca.yaml
id: full-lca
title: 完整 LCA
plan_file: main_plan.md
max_redos: 2
nodes:
  - lca-intake
  - lca-bom
  - lca-mapping
  - id: lca-report-short            # 内联节点
    title: 简报
    requires: [mapping/mapping.json]
    produces: [{spec: lca-report, path: report/report.md}]
    agents: {executor: executor}
    flow: {start: executor, edges: [{from: executor, when: done, to: done}]}
```
```yaml
# harness/workflows/orchestrations/revise-lca.yaml
id: revise-lca
plan_file: revise_plan.md
start_rev: next          # 每个节点从已有最大 rev + 1 起跑
max_redos: 1
nodes: [lca-bom-revise, lca-mapping-revise, lca-report-revise]
```
```yaml
# harness/workflows/nodes/lca-mapping.yaml
id: lca-mapping
title: 背景映射与 LCI
requires: [bom/bom.json]
produces: [{spec: lca-mapping, path: mapping/mapping.json}]
inject: [rules/lca/mapping.yaml, rules/lca/openlca.yaml]
agents:
  executor: {agent: executor, max_turns: 120, tools: {mcp: [control_openlca]}}   # 覆盖只作用于本节点
  reviewer: reviewer                                                             # 短名
  checker:                                                                       # 内联 agent
    prompt: 只核对单位换算，用 submit 报 approve/reject。
    deliver: {submit: verdict}
flow:
  start: executor
  max_steps: 12
  edges:
    - {from: executor, when: done, to: reviewer}
    - {from: executor, when: blocked, to: blocked}
    - {from: executor, when: redo_upstream, to: reviewer}
    - {from: reviewer, when: approve, to: done}
    - {from: reviewer, when: reject, to: executor, max: 3}
    - {from: reviewer, when: approve_redo_upstream, to: redo_upstream}
    - {from: reviewer, when: terminate, to: failed}
```
```yaml
# harness/workflows/agents/reviewer.yaml
title: 角色：审核者
prompt: |
  - 对照 <plan>、<deliverable_*>、<redo_policy> 审核；只读。
  - verdict：approve / reject（issues 逐条 where/problem/expected）/ approve_redo_upstream（仅当执行者请求回溯且符合判据）/ terminate（reason）。
access: {read: {knowledge: true, artifacts: true}, write: {}}
deliver: {submit: verdict, max_nudges: 2, max_turns: 80, timeout_min: 120, max_rejections: 5}
```
约定不变：agent 短名、`{agent: executor, ...}` 覆盖不改模板、`nodes:` 名字和内联对象混排、`rules/` 只放注入规则。
内联 agent 的键名不再限定 executor/reviewer；但 `start` 节点的 deliver.submit 必须是 `artifact`。

## 6. 事件与活动流（并入 #1）

events.jsonl 每行一个结构化记录；GUI 活动流直接用这些记录（不再拼文本再正则解析）。公共字段：
`seq`（单调递增）、`ts`、`run_id`、`kind`、`node?`、`rev?`、`agent?`、`attempt?`、`step?`。

| kind | 额外字段 |
|---|---|
| run_start / run_end | workflow, nodes / status, reason |
| queue_append | items:[{node,rev}], requested_by, target |
| node_start / node_end | requires_resolved / outcome, reason |
| turn_start / turn_end | model, resume / submitted, abort_reason, error |
| assistant_text | text（截断，长文本进 blobs） |
| tool_call / tool_result | tool, summary, is_error, handoff |
| submit | status 或 verdict, 关键字段（summary/issues 数/target_node） |
| submit_rejected | errors |
| host_checks | ok, errors |
| route | from, when, to, back_edge_count |
| redo_requested / redo_approved / redo_refused | target, artifact, field / reason |

- 会话内容（assistant_text、tool_*）由 pi-runtime 现有 `activity.ts` 产出，宿主统一编号写入同一 events.jsonl；`progress_view.py` 删除。
- `/api/workflow/progress?after_seq=` 返回 `{status, current_node, rev, items, next_seq}`；`/api/workflow/activity` 删除。
- 前端：`agent-stream.tsx` 按 item 渲染现有块（同 DOM、同 class），`activity-summary.tsx` 按 `(node, rev, agent, attempt)` 聚合；rev>0 的节点标题显示为 `lca-bom（重做 1）`——只改已有标题文字，不加元素。

## 7. 启动规格（并入 #2）

`SessionLaunchSpec` 以 Python dataclass 为单一来源，`src/scripts/export_contracts.py` 导出 `session_launch_spec.schema.json` 和 `pi-runtime/src/spec.generated.ts`；测试保证导出结果与已提交文件一致。
字段只保留 v5 用到的：`schema_version=2, run_id, node, rev, agent, attempt, session_key, model_profile, system_sections, turn_context, knowledge_bindings, resource_bindings{project_root, credentials_dir}, mcp_bindings, permission_policy, session_storage`；
删除 `stage_id, assignment_id, execution_id, bundle_hash, input_snapshot_hash`，宿主诊断字段（prompt_segments 等）移出 spec。pi-runtime 加载时按 schema 校验。

## 8. 要删除的现有代码

- `runner.py`：`_run_node` 的手写 while 状态机、`_outcome`、`_feedback`（改为 state.feedback + 事件）、`TurnResult`/`TurnRequest` 中的 `round`（改 `attempt`）、`_drop_unfinished_revisions`、revise 分支的 `prepare_fresh` 特例、`sessions_started` 手动 resume 判定（改为 state.attempts）。
- `config.py`：`OUTCOMES`、`Edge.on`、`Flow.max_rounds`、`Node.transition`、`Node.revision`、`Workflow.revise_of`、`AGENT_KEYS` 限定。
- `revisions.py`：`allocate/load/save/node_rev/effective/clear` 与 `revisions.json`，只留 `split/rev_name/rev_path/versions/latest`。
- submit MCP：`ok|stop`、`pass|reject|stop` 两个旧签名。
- `progress_view.py` 整个文件；`/api/workflow/activity`；前端 `isProgressTag/parseTag` 与文本分块。
- `session_launch_spec.schema.json` 和 `types.ts` 的手写定义（改为导出）。
- 所有节点 YAML 的旧 `flow.edges[].on` 写法（destructive，全部重写）。

## 9. 提交计划

1. 依赖与骨架：加 `langgraph`；LangSmith 显式关闭 + doctor 检查；新 `flow` 模型与 YAML 校验（file:line）；旧 Flow 删除；全部节点 YAML 重写。
2. submit 新 schema（MCP + 宿主双校验），`approve_redo_upstream` 前置条件。
3. 内层图：`node_graph.py` 构建 StateGraph，调用 `run_turn`，RetryPolicy，max_steps / 回边 max。
4. 外层队列：`runner.py` 重写为队列 + redo 追加 + `max_redos` + rev 目录/命名 + `queue.json` 续跑；revise-lca 改 `start_rev: next`，删 `revisions.py` 多余部分。
5. spec `upstream` 段 + `<redo_policy>` prompt 生成。
6. 事件与活动流（#1）：统一 events schema + seq；progress API 改 items；前端切换（外观不变）；删 progress_view。
7. 启动规格（#2）：Python 源 + 导出脚本 + 漂移测试 + pi-runtime 校验；字段精简。
8. 文档：DESIGN.md / GUI.md / ISSUES.md。

每步后：pytest、web typecheck + test、pi-runtime tsc + test、doctor。serve 只在 Du Yuan 指示后切换。

## 10. 测试清单（fake pi，临时目录）

| 用例 | 断言 |
|---|---|
| 一次通过 | 节点 passed；事件 submit(done)→route→submit(approve)→node_end |
| 驳回后通过 | executor attempt 2 的 prompt 含 issues；结果 passed |
| 驳回超上限 | 回边 max=3 用尽 → failed: back_edge_limit，run 停 |
| blocked | 不调 reviewer；run failed，status_reason = reason |
| 回溯获批 | 04 请求 03 → 队列 `[03r1, 04r1, 05]`；产物 `bom.rev1.json` 存在、原文件不变；04r1 的 requires 解析到 rev1 |
| 回溯被 reviewer 驳回 | 回 executor，意见要求自修；队列不变 |
| 回溯超 max_redos | 第 3 次请求 → failed: redo_limit |
| 回溯目标非法 | submit 被 MCP 拒收（target 不在之前） |
| 未提交 | failed: no_submit（及 max_turns/timeout 细分） |
| 传输错误重试 | 第一次 TransientTurnError，RetryPolicy 重试后通过 |
| max_steps | 无限回边被 max_steps 截断 |
| YAML 错误 | 未知 when、回边无 max、终点不可达、未知 agent 名 → 报错含 `file:line` |
| 续跑 | 中途停止后从 queue.json 第一个未完成项继续，已过节点不重跑 |
| LangSmith 关闭 | 运行时环境变量为 false，无外部请求 |
| 契约导出 | export_contracts 输出与已提交文件一致 |

## 11. 与 #1 / #2 的关系

两项都改同一批代码（runner 事件、pi_driver 启动），按 Du Yuan 决定并入本次重建（§6、§7、提交 6、7），不单独实施；`docs/refactor/v5/SIMPLIFY_PLAN.md` 中 #1、#2 以本文为准（#2 改为 Python 源 + 导出脚本，不引入代码生成依赖）。

## 12. 待 Du Yuan 决定

1. 重做段的位置：本文定为"紧接请求节点之后执行，原后续节点顺延"（等价于插队）；如果坚持字面的"追加到队尾"，下游节点（如 05）会先于重做段执行、读到旧版本——是否接受？
2. `max_redos` 默认 2、按整次运行计数，还是按"每个目标节点"计数？
3. 回溯目标默认允许任意更早节点，还是必须在 spec `upstream.may_redo` 中列出？
4. 无 reviewer 的节点提交 redo_upstream：本文定为失败，是否改成宿主直接批准？
5. 节点内是否需要真正的并行 agent（`join`）？不需要的话可去掉该语法，进一步简化。
6. revise-lca 是否保留为单独 orchestration（`start_rev: next`），还是改成"对 full-lca 从某节点起重做"的一个入口？
7. 重做节点的 executor 是否续接上一次 rev 的会话（省 token）还是全新会话（本文默认全新，prompt 附带 redo 理由与旧产物路径）？
