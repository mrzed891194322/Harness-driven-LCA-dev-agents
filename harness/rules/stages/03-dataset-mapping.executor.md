# 03 背景映射与 LCI（执行）

按共有契约完成完整 mapping、全部必做情景的 LCI，以及可复算的换算和适配说明。背景匹配遵守映射规则；区分正式查询到的背景实体与本次创建的前景实体。

定稿后做正式 Provider–Flow 验证，保留查询与验证引用；不执行导入。返工修复指出的问题及关联实体、目标量和文字说明，再提交完整产物，避免只改 JSON 或只改说明。

LCI 目录由你直接写在正式位置，定稿并做完最后一次 provider 验证后用 `submit("LCI")` 原位验收（含交换单位与 provider 参考单位组一致性）；mapping 用 `submit("process-mapping", data)` 交付，正式路径只由 spec_mcp 写入。本轮最后一动作为 spec_mcp 的 `submit_handoff` 交卷。提交 `role=executor` 的 handoff，artifacts 列出 mapping 与 LCI（含 human_readable_mapping.md）。无法解决的关键数据或工具缺口明确失败，不以无依据代理补齐。
