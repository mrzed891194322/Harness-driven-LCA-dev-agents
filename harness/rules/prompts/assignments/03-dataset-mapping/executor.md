# 03 背景映射与 LCI（执行）

按共有契约完成完整 mapping、全部必做情景的 LCI，以及可复算的换算和适配说明。背景匹配遵守映射规则；区分正式查询到的背景实体与本次创建的前景实体。

定稿后做正式 Provider–Flow 验证，保留查询与验证引用；不执行导入。返工修复指出的问题及关联实体、目标量和文字说明，再提交完整产物，避免只改 JSON 或只改说明。

本轮最后一动作为交卷：优先 `submit_handoff`，或写入运行上下文 `handoff_path` 的 JSON。提交 `role=executor` 的 handoff，artifacts 列出 mapping 与 LCI（含 human_readable_mapping.md）。无法解决的关键数据或工具缺口明确失败，不以无依据代理补齐。
