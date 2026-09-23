# 04 openLCA 计算与报告

在已审模型上预检、导入、读回、计算并解释结果。执行后审查，最多 3 轮；写库失败受控停止。

## 首次执行与导入边界

以下写入与计算步骤仅供 executor/reviser；reviewer 不补做。

1. 核对全部必做情景和分析：缺模型需上游审查。导入、计算、LCIA 类别总量等硬工具交付缺能力则失败；解释类要求（贡献/热点等）无分解工具时按规则 `llm_inferred` + 出处表落实，不用限制段冒充已完成、也不因 plan 未写 fallback 许可而失败。首次访问 IPC 按工具规则做 health_check。
2. 调用 `preflight_import_lci`，保留 preflight_id、库名声明及身份来源、目标分类、LCI 目录和模型内容。whole-lca/revise-lca 只导入规范的 `workspace/outputs/LCI`。
3. 调用 `import_lci(request_id=本次稳定请求ID, preflight_id=本次预检ID)`。启动工作流已授权导入同一已审、已预检范围，不额外请求确认；模型或范围变化必须停止。仅旧预检失效而已审模型和范围未变时可重新预检，不能越过 03 审查。
4. 导入完成后，用 `get_model_graph` 核对每个 Product System、新建前景实体及预期连接。按需要正式回读参考过程与流，核实数量基准。
5. 写计算计划并调用 `calculate_product_system`，完整结果由工具落盘。最后按模板生成报告，调用 `render_report_tables` 生成三组表格。

导入超时不是服务端取消：用原 request_id 调用 `get_import_operation`，不生成新请求、不盲目重导、不使用 legacy CLI 或直接脚本绕过门禁。running 只继续有界查询；indeterminate、部分失败或无法确认终态则受控停止。reused 只返回同请求日志，不证明数据库当前未被外部修改。长调用使用 MCP 的 timeout_sec，范围以工具签名为准，不使用外层 shell timeout。

## 计算计划与报告

首次计算前写计算计划，保持 calculations 数组；每项含 product_system、impact_method 和 amount，可选 allocation、regionalized、costs、parameters 与接口一致。同一 Product System+方法唯一；不同模型情景对应在 03 已审的不同 Product System。覆盖全部声明系统和必做分析，不仅覆盖已经算过的目标。

product_system 使用导入后正式确认的 UUID，impact_method 必须正式查询并符合用户指定要求。amount 是实现功能单位所需的参考流数量，依据 03 换算链及已核实的默认参考单位填写，不能机械复制 1.0。将实际调用、raw 设置和报告分母逐项核对；单位无法核实或设置不对应功能单位则不计算/不通过。不要把 Product System 的 targetAmount 当成实际调用已使用的 amount。

报告保留全部模板章节及三组 lca 标记，补充：

- 研究要求落实表：要求及计划/修订位置、必做/可选、情景或分析、完成情况和证据位置（可指向出处表或 raw；完成情况可标 `tool_backed` / `llm_inferred`）。
- 功能单位—参考流—amount 对照及模型范围，前景清单与映射回指 item_id。
- 主情景比较、必做敏感性结果、完整性/一致性与不确定性讨论；限制、代理、排除和未解决项。
- 出处表：主张、provenance（仅 `tool_backed` 或 `llm_inferred`）、依据路径、局限。

生成区数值不手改；额外计算和解释写在正文并保留公式与 raw 来源，不能用事后缩放掩盖错误的原始计算量。当前工具只提供 LCIA 类别汇总，不提供过程贡献分解；贡献/热点类主张无分解 raw 时写者按规则填 `llm_inferred` 出处表行，不得伪装成工具测得的贡献百分比或过程贡献分解表。LCIA 类别总量本身仍必须来自工具 raw，不能用叙述顶替计算失败。

## 验收与返工

报告须准确可读、中文解释完整，数值能回链本 run 的正式 raw，全部必做要求有证据落实（解释类可经出处表）。导入失败、断链、空结果、resource_released 不为 true、错误计算基准、硬计算类缺口，或出处表缺失/provenance 越界，均不得通过。完成表格不等于完成研究解释。

主编排在合法 ok 和产物齐全后运行 report 检查，再由 reviewer 判断需求覆盖、量纲和结论依据。机器检查不证明这些方法条件。

attempt>1 先调用 `get_rework_status`：eligible=true 且 rework_scope=report_only 时只修正文/生成表格，不调用 health/preflight/import/graph/calculate。已审模型未变而计算计划变化时，核对基准并重算相关目标；证据丢失按具体缺口补做。模型、BOM、mapping、计划或来源相对已审核快照变化则需上游审查，不在 04 强行重导。必做模型情景遗漏也不能在 04 直接补模型。

新 revise run 首次完整执行上述流程，不跨 run 沿用通过状态。范围变化、不可恢复失败或三次审查未过则 failed；reviewer 通过且编排验收成功后完成。

## 方法审查提示（示例）

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
