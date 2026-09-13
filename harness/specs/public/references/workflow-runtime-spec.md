# Whole-LCA 运行说明

工作流编成四个编号阶段，语义上是 **1 个启动门禁 + 3 个 LCA 业务步**。没有 JSON Schema 业务门禁；离线工具生成校验证据，不代替 reviewer 判断。阶段推进由 Python 主编排器（LangGraph）负责，agent 只完成本轮被委派的任务。

## 阶段

1. `01-intake-gate`：初始化检查。不是 ISO LCA 步骤。只派审查任务，不派写者任务。一次未通过即 `failed`。
2. `02-inventory-extraction`：从用户资料提取前景 BOM。
3. `03-dataset-mapping`：把 BOM 映射到活动库 Process/Flow/Provider，并写出可导入 LCI。通过前不 import。
4. `04-openlca-reporting`：预检、导入、读回、LCIA、写报告。

`revise-lca` 是同一套 01–04。02–04 的写者换成 `reviser`（任务文件为各包 `reviser.md`），审查仍由 `reviewer` 决定是否推进。修订补充契约在各包 `references/revise.md`，由 YAML `spec_additions` 注入。不要覆盖 `plan.md`。审查时用户意图优先于单纯正确性。

进入某阶段时才把该阶段共有契约与角色任务交给对应会话；启动只把本文纳入公共协议，不预读编号包全文到无关会话。

## 路径

- 输入：`workspace/inputs/plan.md`（revise 另加 `workspace/inputs/revise.md`）
- 知识：默认 `harness/knowledge/`；任务也可使用 YAML 注册并绑定的工具来源
- 状态：`workspace/memory/manifest.json`、`workspace/memory/reviews/`、`workspace/memory/handoffs/`；编排检查点在 `workspace/memory/` 的 SQLite；可选 `checklist.md`
- 前景产物：`workspace/outputs/inventory/extracted-bom.json`、`extracted-bom.md`、`process-mapping.json`。GUI「工作细节」只渲染两份 JSON，不读 `.md`
- LCI：`workspace/outputs/LCI/`（`flows/`、`processes/`、`product_systems/`，外加 `human_readable_mapping.md`）
- 报告：`workspace/outputs/reports/lca_report.md`；MCP 完整业务结果由工具落在 `reports/runs/<run_id>/<stage>/<attempt>/<call_id>/raw.json`。revise 覆盖该报告并追加修订三节。

## 运行上下文

主编排在每轮任务输入中提供结构化运行数据，不为此使用模板语言：

| 字段 | 含义 |
| --- | --- |
| run_id | 一次工作流运行。LangGraph `thread_id` 与此相同 |
| task | `whole-lca` 或 `revise-lca` |
| stage | 当前阶段 id |
| role | `executor`、`reviser` 或 `reviewer` |
| assignment | YAML 中的任务 id，如 `03-dataset-mapping.executor` 或 `03-dataset-mapping.reviser` |
| attempt | 当前阶段轮次，从 1 起。轮次不构成新会话 |
| fix_instructions | 审查未通过时交给写者会话的返工意见；复审时也可附修改说明路径 |

会话按「一次运行 × 一个阶段 × 一个角色任务」关联。01 只创建评估会话。revise 的 02–04 写者会话键为 `stage:reviser`。

## 循环

01：只派审查。`passed` 进入 02；`failed` 停止。revise 的 01 另核 `revise.md` 与上一轮已完成产物。

02–04：每阶段先写者后审查。未通过且未满该阶段 `max_attempts` 则在原写者会话返工，再在原评估会话复审；达到上限仍失败则 `failed`。04 通过后 `completed`。

审查笔记写 `workspace/memory/reviews/<stage>-<n>.md`，写明 `passed` 或 `failed`、摘要、要改什么。由主编排根据 handoff 落盘。

## handoff

Agent 完成本轮后写入 `workspace/memory/handoffs/<stage>-<role>-<attempt>.json`，`schema_version` 为 `1`，字段：

- `role`、`stage`、`attempt`
- `status`：executor / reviser 为 `ok` / `failed` / `blocked`；reviewer 为 `passed` / `failed`
- `status_reason`：非空说明
- `fix_instructions`：审查失败时必须给出，定位到产物、条目或证据；revise 时先写用户意图缺口
- `artifacts`：本轮提交或核过的路径列表

检查点和 manifest 由主编排维护。agent 不维护 SDK 会话映射，不决定阶段推进。

失败时必须提供：失败对象、已核对证据、建议修正或为何不可恢复。缺少产物、`blocked` 或审查失败不得被当成完成。

## 状态

`manifest.json` 至少包含：

- `status`：`running` | `failed` | `completed`
- `current_stage`：当前阶段 id 或 `null`
- `status_reason`：终止时非空说明
- `run_id`：本次运行 id

不要设 `needs_input` / `awaiting_confirmation`。运行中不征求用户建模决定。可留档的匹配由写者自行选择并写入 BOM/映射/报告。

恢复运行时以检查点为准，不以 manifest 单独作为恢复依据。worker 调用期间中断且检查点仍标 `in_flight` 时，主编排记为 `failed`，不自动重发任务。

每个角色首次访问 openLCA 前调用 `health_check`；仅离线报告返工或审查不访问 IPC 时无需探测。失败则如实上报。

示例见 `references/examples/`。

## v2 校验证据与返工

详细契约见 `references/evidence-contract.md`。运行上下文提供 source_manifest、evidence_manifest_ref 和当前检查摘要；完整证据按需读取。handoff 可增加路径字符串 checks_ref、evidence_manifest_ref，以及 rework_scope（none/report_only/calculation_changed/model_changed），不可自行伪造工具检查状态。

编排器仅保存 reviewer 对当前产物的通过决定；工具据此识别已审核模型是否变化。检查状态为 not_run/passed/failed/stale，不等于阶段状态。旧检查点不续跑 v2，旧 raw 只作历史资料。新 revise 仍完整执行 01–04，不复用跨 run 的通过状态。
