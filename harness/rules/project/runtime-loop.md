# Whole-LCA 阶段运行环（项目约定）

工作流编成四个编号阶段，语义上是 **1 个启动门禁 + 3 个 LCA 业务步**。离线工具生成校验证据，不代替 reviewer 判断。阶段推进由主编排器负责，agent 只完成本轮被委派的任务。通用 handoff 字段与协议由主编排注入，不在此重复。

## 阶段语义

1. `01-intake-gate`：初始化检查。不是 ISO LCA 步骤。只派审查任务，不派写者任务。一次未通过即 `failed`。
2. `02-inventory-extraction`：从用户资料提取前景 BOM。
3. `03-dataset-mapping`：把 BOM 映射到活动库 Process/Flow/Provider，并写出可导入 LCI。通过前不 import。
4. `04-openlca-reporting`：预检、导入、读回、LCIA、写报告。

`revise-lca` 是同一套 01–04。02–04 的写者换成 `reviser`，审查仍由 `reviewer` 决定是否推进。修订补充契约在各阶段 `*.revise.md` 规则中。两种工作流均须满足共同方法规则中的研究要求和正确性，修订不覆盖 `plan.md`。

进入某阶段时才把该阶段共有契约与角色任务交给对应会话；启动不把无关阶段全文预读到会话。

## 产物与排障路径（LCA 约定）

- 输入：`workspace/inputs/plan.md`（revise 另加 `workspace/inputs/revise.md`）
- 知识：以工作流 YAML 绑定的 `knowledge_sources` / `source_manifest` 为准
- 状态：`workspace/memory/manifest.json`、`workspace/memory/reviews/`、`workspace/memory/handoffs/`；编排检查点在 `workspace/memory/` 的 SQLite
- 排障留档：`workspace/memory/logs/<run_id>/`；运行时 MCP 渲染在 `workspace/tmp/mcp-render/`
- 前景产物：`extracted-bom.json` / `.md`、`process-mapping.json`。GUI「工作细节」只渲染两份 JSON
- LCI：`workspace/outputs/LCI/`（`flows/`、`processes/`、`product_systems/`，外加 `human_readable_mapping.md`）
- 报告：`lca_report.md`；MCP 完整业务结果在 `reports/runs/<run_id>/.../raw.json`。revise 覆盖该报告并追加修订三节

## 循环（LCA）

01：只派审查。`passed` 进入 02；`failed` 停止。revise 的 01 另核 `revise.md` 与上一轮已完成产物。

02–04：每阶段先写者后审查。写者合法 `ok` 且产物齐全后，主编排运行本阶段确定性检查（inventory / mapping / report）；检查失败则在原写者会话返工（计 attempt）。检查通过后再派审查。审查未通过且未满该阶段 `max_attempts` 则在原写者会话返工，再在原评估会话复审；达到上限仍失败则 `failed`。04 通过后 `completed`。

确定性检查通过不推进阶段；只有合法 reviewer handoff 的 `status` 才推进。审查笔记由主编排在 hard gate 与 hooks 结束后按最终可审计结果落盘。

## 终止与自主决策

`manifest.json` 的 `status` 为 `running` | `failed` | `completed`。不要设 `needs_input` / `awaiting_confirmation`。运行中不征求用户建模决定；在共同方法规则允许的范围内自主选择并留档。无法满足明确要求、存在关键未解决缺口或缺少必做**硬**工具能力时，以现有失败协议受控停止。解释类要求按阶段契约允许 `llm_inferred` + 出处表 fallback，不得因用户未在 plan 写许可而停止。

## 证据与同 run 返工（LCA）

检查 status 为 not_run/passed/failed/stale，不等于阶段状态。MCP 调用 status 与 handoff status 三者不得互相替代。

- inventory：非空 items、必填字段、唯一 item_id、extraction_status 枚举、来源定位以及本地文件存在性
- mapping：BOM/mapping item_id 覆盖、LCI 方向/参考输出/前景引用等语义检查，以及背景 exchange 的 Provider+Flow 正式验证证据
- report：同 run 的成功导入、每个 Product System 的无断链图、calculation-plan 中各目标和方法的非空计算及资源释放、raw 校验和、三组报告生成表格一致性

上述检查不证明单位换算、功能等价性、源数据完整或语言合格，也不证明计划中的全部情景已被建模或 amount 对应功能单位。

复用限定相同 run_id、同阶段 attempt>1。已审核 03 产物指纹变化则 model_changed，不在 04 绕过上游审查。calculation-plan 改变使计算证据失效；raw 缺失/校验和错误必须补证据，不能标记 report_only。仅正文变化且已有模型、设置和 raw 均有效时允许 report_only，全程不调用 IPC。

可选 handoff 字段 `checks_ref` / `evidence_manifest_ref` 为路径字符串；`rework_scope` 为 none / report_only / calculation_changed / model_changed。不可自行伪造工具检查状态。

审查 `passed` 后执行的 lifecycle hooks（如 mapping 阶段 `record_acceptance`）应尽量幂等；运行器在 hook 异常时 fail-closed。openLCA 访问遵守绑定的工具规则；导入和同 run 返工顺序以 04 阶段规则为准。新 revise 仍完整执行 01–04，不复用跨 run 的通过状态。
