# v2 证据与检查契约

## 分层与状态

MCP status 表示调用结果：success/failed/running/indeterminate/not_found。检查 status 为 not_run/passed/failed/stale。阶段 handoff 继续使用 executor/reviser ok/failed/blocked 与 reviewer passed/failed。三者不得互相替代。

工具接口、参数类型和响应由 tools 实现；本契约规定证据和验收含义。编排器保存 reviewer 的当前产物通过快照，不运行业务校验，也不凭检查 passed 推进。

## 留档

完整业务结果由工具原子写入 `workspace/outputs/reports/runs/<run_id>/<stage>/<attempt>/<call_id>/raw.json`，只追加不覆盖。相应 envelope 带 schema_version=2、status、summary、counts、errors、warnings、artifacts、duration_ms。artifact 为 path（相对 workspace）、sha256、size_bytes。默认响应不超过 32 KiB，分页或附件保存省略的明细；不得丢掉真实失败。

`workspace/memory/evidence/<run_id>/manifest.json` 保存本运行所有调用及审核快照；sources.json 保存资料清单。checks/<profile>.json 为当前状态，checks/history 保存历次执行记录。工具生成并维护这些记录，agent 只在 handoff 引用路径。

## 检查

记录包括 check_id、checker_version、status、inputs（依赖文件指纹与证据引用）、executed_at、summary、errors、warnings。检查器版本、依赖文件或引用变化时状态变为 stale；缺失依赖不得视为已验证。数据库结果只证明调用时的观测，不能证明数据库身份或其后未被外部修改。

- inventory：非空 items、必填字段、唯一 item_id、extraction_status 枚举、来源定位以及本地文件存在性。远程文档只检查定位格式，不把离线检查当成可访问性验证。
- mapping：BOM/mapping item_id 覆盖、LCI 方向/参考输出/前景引用等已有语义检查，以及背景 exchange 的 Provider+Flow 正式验证证据。
- report：同 run 的成功导入、每个 Product System 的无断链图、calculation-plan 中各目标和方法的非空计算及资源释放、raw 校验和、三组报告生成表格一致性。

上述检查不证明单位换算、功能等价性、源数据完整或语言合格。reviewer 必须独立判断；正文中的额外数字也需 reviewer 回链。

## 返工

复用限定相同 run_id、同阶段 attempt>1。已审核 03 产物指纹变化则 model_changed，不在 04 绕过上游审查。calculation-plan 改变使计算证据失效；raw 缺失/校验和错误必须补证据，不能标记 report_only。仅正文变化且已有模型、设置和 raw 均有效时允许 report_only，全程不调用 IPC。

handoff 可选 checks_ref/evidence_manifest_ref 是路径字符串，rework_scope 为 none/report_only/calculation_changed/model_changed。旧 raw 留作历史；旧 checkpoint 不续跑 v2。
