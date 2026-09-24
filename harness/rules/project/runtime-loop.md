# Whole-LCA 运行环（项目约定）

离线工具生成校验证据，不代替 reviewer 判断。阶段推进由主编排器负责，agent 只完成本轮被委派的任务。通用 handoff 字段与协议由主编排注入，不在此重复。具体阶段顺序、assignment 绑定与工具注册以工作流 YAML 为准，本文件不复述拓扑。

## 产物与排障路径（LCA 约定）

- 输入：`workspace/inputs/plan.md`（revise 另加 `workspace/inputs/revise.md`）
- 知识：以工作流 YAML 绑定的 `knowledge_sources` / `source_manifest` 为准
- 状态：`workspace/memory/manifest.json`、`workspace/memory/reviews/`、`workspace/memory/handoffs/`；编排检查点在 `workspace/memory/` 的 SQLite
- 排障留档：`workspace/memory/logs/<run_id>/`；运行时 MCP 渲染在 `workspace/tmp/mcp-render/`
- 前景产物：`extracted-bom.json` / `.md`、`process-mapping.json`。GUI「工作细节」只渲染两份 JSON
- LCI：`workspace/outputs/LCI/`（`flows/`、`processes/`、`product_systems/`，外加 `human_readable_mapping.md`）
- 报告：`lca_report.md`；MCP 完整业务结果在 `reports/runs/<run_id>/.../raw.json`。revise 覆盖该报告并追加修订三节

## 证据与返工政策

检查 status 为 not_run/passed/failed/stale，不等于阶段状态。MCP 调用 status 与 handoff status 三者不得互相替代。

- inventory：非空 items、必填字段、唯一 item_id、extraction_status 枚举、来源定位以及本地文件存在性
- mapping：BOM/mapping item_id 覆盖、LCI 方向/参考输出/前景引用等语义检查，以及背景 exchange 的 Provider+Flow 正式验证证据
- report：同 run 的成功导入、每个 Product System 的无断链图、calculation-plan 中各目标和方法的非空计算及资源释放、raw 校验和、三组报告生成表格一致性

上述检查不证明单位换算、功能等价性、源数据完整或语言合格，也不证明计划中的全部情景已被建模或 amount 对应功能单位。

复用限定相同 run_id、同阶段 attempt>1。已审核 mapping 产物指纹变化则 model_changed，不在报告阶段绕过上游审查。calculation-plan 改变使计算证据失效；raw 缺失/校验和错误必须补证据，不能标记 report_only。仅正文变化且已有模型、设置和 raw 均有效时允许 report_only，全程不调用 IPC。

可选 handoff 字段 `checks_ref` / `evidence_manifest_ref` 为路径字符串；`rework_scope` 为 none / report_only / calculation_changed / model_changed。不可自行伪造工具检查状态。

审查 `passed` 后执行的 lifecycle actions（如 mapping 阶段 `record_acceptance`）应尽量幂等；运行器在异常时 fail-closed。openLCA 访问遵守绑定的工具规则。新 revise 仍完整执行工作流 YAML 中的全部阶段，不复用跨 run 的通过状态。

## 终止与自主决策

`manifest.json` 的 `status` 为 `running` | `failed` | `completed`。不要设 `needs_input` / `awaiting_confirmation`。运行中不征求用户建模决定；在共同方法规则允许的范围内自主选择并留档。无法满足明确要求、存在关键未解决缺口或缺少必做**硬**工具能力时，以现有失败协议受控停止。解释类要求按阶段契约允许 `llm_inferred` + 出处表 fallback，不得因用户未在 plan 写许可而停止。
