# v2 证据与检查契约

## 分层与状态

MCP status 表示调用结果：success/failed/running/indeterminate/not_found。检查 status 为 not_run/passed/failed/stale。阶段 handoff 继续使用 executor/reviser ok/failed/blocked 与 reviewer passed/failed。三者不得互相替代。

工具接口、参数类型和响应由 tools 实现；本契约规定证据和验收含义。编排器在写者合法提交后运行确定性检查，保存 reviewer 的当前产物通过快照，不凭检查 passed 推进阶段。

## 留档

完整业务结果由工具原子写入 `workspace/outputs/reports/runs/<run_id>/<stage>/<attempt>/<call_id>/raw.json`，只追加不覆盖。相应 envelope 带 schema_version=2、status、summary、counts、errors、warnings、artifacts、duration_ms。artifact 为 path（相对 workspace）、sha256、size_bytes。默认响应不超过 32 KiB，分页或附件保存省略的明细；不得丢掉真实失败。

`workspace/memory/evidence/<run_id>/manifest.json` 保存本运行所有调用及审核快照；sources.json 保存资料清单。checks/<profile>.json 为当前状态，checks/history 保存历次执行记录。主编排在写者 handoff 后运行对应 profile 的检查；agent 可选用同一工具做提前反馈，只在 handoff 引用路径。

## 检查

记录包括 check_id、checker_version、status、inputs（依赖文件指纹与证据引用）、executed_at、summary、errors、warnings。检查器版本、依赖文件或引用变化时状态变为 stale；缺失依赖不得视为已验证。数据库结果只证明调用时的观测，不能证明数据库身份或其后未被外部修改。

- inventory：非空 items、必填字段、唯一 item_id、extraction_status 枚举、来源定位以及本地文件存在性。远程文档只检查定位格式，不把离线检查当成可访问性验证。
- mapping：BOM/mapping item_id 覆盖、LCI 方向/参考输出/前景引用等已有语义检查，以及背景 exchange 的 Provider+Flow 正式验证证据。
- report：同 run 的成功导入、每个 Product System 的无断链图、calculation-plan 中各目标和方法的非空计算及资源释放、raw 校验和、三组报告生成表格一致性。

上述检查不证明单位换算、功能等价性、源数据完整或语言合格，也不证明计划中的全部情景已被建模或 amount 对应功能单位。reviewer 必须独立判断；正文中的额外数字也需 reviewer 回链。新增的方法说明沿用既有 Markdown 产物，不扩展机器检查能力或 JSON 接口。

## 返工

复用限定相同 run_id、同阶段 attempt>1。已审核 03 产物指纹变化则 model_changed，不在 04 绕过上游审查。calculation-plan 改变使计算证据失效；raw 缺失/校验和错误必须补证据，不能标记 report_only。仅正文变化且已有模型、设置和 raw 均有效时允许 report_only，全程不调用 IPC。

handoff 可选 checks_ref/evidence_manifest_ref 是路径字符串，不是写者 `ok` 的前提。rework_scope 为 none/report_only/calculation_changed/model_changed。旧 raw 留作历史；旧 checkpoint 不续跑 v2。

## 方法审查案例

以下为 reviewer 的验收示例，不是新增自动检查。数值仅用于示例，不能写成通用建模假设。

| 情景 | 审查预期 |
| --- | --- |
| 功能单位 1,000 瓶，每瓶参考输出 1.065 kg，默认参考单位 kg | 目标及实际计算量应为 1,065 kg；targetAmount=1065 而实际 amount=1，不能当作整个功能单位通过 |
| 65 kg 货物运输 300 km，换为 t·km | 65 × 300 / 1000 = 19.5 t·km；已给运输功时不得再乘质量或距离 |
| 数量未知但填写 0，或工序仅挂到聚合过程而无负荷 | 不通过；要求保留未知标记并解决关键缺口，或核对计划明确允许的排除 |
| 已有背景 UUID 有查询证据；前景 UUID 为本次创建 | 前者核实体和 Provider–Flow，后者核稳定引用与导入读回，不能一律要求创建前查询命中 |
| 指定方法不存在，Agent 换成近似方法 | 不通过；合理地域代理可在功能/技术/单位/系统模型适配且不违背计划时接受 |
| 计划要求 300 km 主情景和 200 km 敏感性，只有主情景结果 | 不通过；必须覆盖敏感性模型与正式结果，不能只写“未执行” |
| 市场已含某段运输，模型重复添加同段运输 | 要求查清覆盖并消除重复；相关元数据不可核查时如实列缺口，不能假称已验证 |
| 仅有类别总量，却声称某过程贡献最大且无出处表或标为 `tool_backed` | 不通过；须有正式分解 raw 才可 `tool_backed`，否则应 `llm_inferred` 并写清局限与依据路径 |
| 出处表为 `llm_inferred`，依据可定位，局限写明非过程贡献分解 | 可通过（解释类）；不因缺贡献 MCP 受控停止 |
| 措辞只能理解为需 openLCA 贡献数值表/百分比或 Monte Carlo 分布，且当前无工具 | 受控停止；叙述不能顶替硬计算交付 |
| 已审模型、计算设置和 raw 有效，仅报告正文返工 | 按 get_rework_status 处理 report_only，不要求重跑 IPC |
