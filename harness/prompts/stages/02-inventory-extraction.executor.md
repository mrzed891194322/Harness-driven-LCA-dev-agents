# 02 前景清单提取（执行）

按共有契约读取声明资料，完成完整 BOM JSON、同批 Markdown 表格、需求与情景清单、数量推导和缺口说明。使用来源与清单规则判断；不查 openLCA、不写 LCI。

返工修正指出的问题及其关联行、合计和说明，保持稳定 item_id，重新提交完整产物，不另起一套清单。无法有据解决的关键缺口如实失败。

两份产物用 spec_mcp 的 `submit` 交付（`extracted-bom`、`extracted-bom-notes`）：草稿可先写在 `workspace/tmp/`，正式路径只由 spec_mcp 写入；验收不通过就按返回的错误清单修正后重交。本轮最后一动作为 spec_mcp 的 `submit_handoff` 交卷（无 handoff 等于未交卷）。提交 `role=executor` 的 handoff，列出两份产物；ok 表示本阶段工作已完成并落盘等待检查和审查，不自报权威检查计数。无法完成时仍须交卷并 `status` 为 failed/blocked。
