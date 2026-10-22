# v5 简化计划（#1 / #2 / #4，只有方案，未改代码）

前提沿用 v5：破坏式重建，不兼容旧运行/旧格式；保留新运行的节点级续跑；前端外观对齐 `599ed0a`，不加元素。每项拆成独立提交，每步跑三套测试（pytest / web / pi-runtime）。

---

## #1 结构化活动流，替换 progress_view 文本 + 前端正则回解析

**现状**
- `src/backend/v5/progress_view.py` 的 `build()` 把 events.jsonl 与 `tmp/pi-v5/<node>.<agent>/session.jsonl` 拼成**一整段文本**，每块以 `[orchestrator-HH:MM:SS]` 或 `[<node>(<agent>#<n>)-<worker>-HH:MM:SS]` 开头；同时另产一份 activity 事件列表。
- `/api/workflow/progress` 返回 `text` + `offset`/`epoch`/`reset`（按字符偏移增量）；`/api/workflow/activity` 返回事件。
- `components/runs/agent-stream.tsx`（624 行）用 `isProgressTag` / `parseTag` 等正则把文本拆回块、再拆出 node/agent/attempt/worker/time。同一信息在后端序列化成文本、前端再解析回来。

**方案**
1. 后端只产一种记录：`ActivityItem = {seq, ts, source: "orchestrator"|"agent", node?, agent?, attempt?, worker?, kind, text?, tool?, is_error?, handoff?}`。`kind` ∈ `note`（编排器文本）、`assistant_text`、`tool_call`、`tool_result`、`turn_end`。现有 activity 事件就是它的子集，合并即可。
2. `/api/workflow/progress` 改为 `{run_id, status, current_node, attempt, status_reason, model, items: ActivityItem[], next_seq}`，客户端带 `after_seq` 增量拉取；`epoch` 用 `run_id`，换运行即重置。去掉字符 `offset` 和 `text`。`/api/workflow/activity` 合并进来后删除。
3. 前端：`agent-stream.tsx` 直接按 item 渲染，删掉 `isProgressTag`/`parseTag`/文本分块；`activity-summary.tsx` 的 `summarizeActivity` 改吃同一 `items`。DOM 和 CSS 不变（同样的块、同样的 class），外观不变。
4. 测试：后端给 `build()` 写 fixture 测 item 序列；前端单测改为喂 items。

**提交拆分**：(a) 后端加 items 字段，与 text 并存一提交，前端不动；(b) 前端切到 items；(c) 删除 text/offset、/activity 和正则。

**风险**：增量语义由字符偏移改为 seq；items 必须按 `(ts, order)` 稳定排序，与现在拼文本的顺序一致。

---

## #2 精简 SessionLaunchSpec，Python / JSON schema / TS 从同一源生成

**现状**
- 三份手写定义：`src/backend/core/contracts/session_launch_spec.py`（dataclass + `to_dict`）、`session_launch_spec.schema.json`（运行时**没人加载**，只有 `$id`）、`src/pi-runtime/src/types.ts`（注释写着 "Mirrors ..."）。改一个字段要同步三处，I-53 改名就是这么改的。
- 字段有冗余：`stage_id`（= node）、`assignment_id`（v5 里等于 `session_key`）、`execution_id` / `bundle_hash` / `input_snapshot_hash`（pi-runtime 不读，只为诊断）；Python 侧还有不下发的 `prompt_segments` / `spec_view*` / `spec_sources`。
- pi-runtime 实际读取：`session_key`、`model_profile`、`run_id`、`agent`、`attempt`、`stage_id`（快照目录名、transcript）、`system_sections`、`turn_context`、`knowledge_bindings`、`resource_bindings.{project_root,credentials_dir}`、`mcp_bindings`、`permission_policy.*`、`session_storage.*`、`schema_version`。

**方案**
1. 单一源：`session_launch_spec.schema.json` 作为源（JSON Schema 2020-12）。
   - TS：用 `json-schema-to-typescript` 生成 `src/pi-runtime/src/spec.generated.ts`，`types.ts` 只 re-export。
   - Python：用 `datamodel-code-generator` 生成 dataclass（或 pydantic）到 `session_launch_spec_generated.py`；宿主专用的诊断字段（`prompt_segments` 等）移到 `pi_driver` 旁边的独立 `LaunchDiagnostics`，不进 spec。
   - 生成脚本 `src/scripts/gen_contracts.py`，加一个测试：重新生成后必须与已提交文件一致（防漂移）。新增开发依赖需 Du Yuan 确认；不想加依赖的话，可以改成手写 Python 为源 + 一个小导出脚本输出 schema 与 TS。
2. 精简字段：`stage_id` → `node`；删 `assignment_id`（用 `session_key`）；`execution_id` / `bundle_hash` / `input_snapshot_hash` 收进 `diagnostics` 可选对象或删掉；`schema_version` 升到 2。破坏式，不兼容 v1。
3. pi-runtime 加载 spec 时用生成的 schema 校验一次（现在完全不校验），错误回给宿主。

**提交拆分**：(a) 生成器 + 漂移测试，字段不变；(b) 字段精简 + version 2；(c) pi-runtime 运行时校验。

---

## #4 整理 `harness/tools/shared/control_openlca/workflow.py`（2850 行）

**现状**
- 一个文件含 LCI 读取/校验、实体计划、预检、导入执行、不确定残留扫描、模型图、计算设置与 LCIA，68 个顶层函数，其中 52 个私有。
- 11 处 `"schema": "whole-lca/..."` 字符串（`lci-validation`、`import-preflight`、`import-operation-status`、`import-report`、`model-graph`、`raw-lcia-results`）：旧工作流名，v5 无人按它分支。
- 导入日志分四层，写在 `operation_dir` 下：`preflights/<id>.json`（预检）、`requests/<run>/<request>.json`（请求→操作索引）、`current.json`（当前操作指针）、`consumed/<preflight>.json`（预检已用标记）、`operations/<op>.json`（正本），另有 `reconciliations/`。`operations.py`（834 行）负责这些；`resume_import_request` 只在 `operations.py` 内部出现，没有 MCP 入口。`attempt_cleanup.py` 的 `cleanup_prior_attempt_imports` 在仓库内无调用方。

**方案**
1. 先删死代码（每项先 `rg` 确认无调用）：`resume_import_request`、`cleanup_prior_attempt_imports` / `attempt_cleanup.py` 中只为它服务的部分，以及 workflow.py 里仅被它们调用的私有函数。
2. 日志收成两层：`preflights/<id>.json` + `operations/<op>.json`。
   - "预检已用" 写进 operation 文件的 `preflight_id` 字段，按 preflight_id 扫 operations 判断（每节点只有几个文件）。
   - `request_id` → operation：同样写进 operation 文件，查时扫描；删掉 `requests/` 与 `current.json`。`get_import_operation` 不传 id 时取最新的 operation（按 `started_at`）。
   - `reconciliations/` 并进 operation 文件的 `reconciliations: []`。
   - 不确定状态（`*.uncertain` 锁标记、running/indeterminate）保留，"超时不盲目重试" 的语义不变。
3. 拆文件（只移动，不改行为）：`lci_inventory.py`（读取/校验/实体计划）、`importer.py`（预检 + 导入 + 残留扫描）、`graph.py`（模型图）、`calculate.py`（计算设置 + LCIA）；`workflow.py` 删除，`main.py` 与 `cleanup*.py` 改 import。
4. `schema` 字符串统一改成 `openlca/<kind>`（或干脆删掉，返回体靠工具名区分）；有测试断言的同步改。
5. 测试：`src/tests/t_harness/tools/control_openlca` 全过；为两层日志加用例（重复 request_id 复用、preflight 重复使用被拒、超时后 `get_import_operation` 能找到 running 操作）。真实 openLCA 只在分类 `202606-harness-agent-LCA` 下手动回归一次导入。

**提交拆分**：(a) 删死代码；(b) 拆文件（纯移动）；(c) schema 字符串；(d) 日志两层化（行为变化，单独一提交，附测试）。

**风险**：(d) 改变导入幂等的实现，是这三项里风险最高的；放在最后，单独回归。
