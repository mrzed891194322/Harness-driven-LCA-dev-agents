# 03 背景映射与 LCI（执行）

按共有契约完成完整 mapping、全部必做情景的 LCI，以及可复算的换算和适配说明。背景匹配遵守映射规则；区分正式查询到的背景实体与本次创建的前景实体。

定稿后做正式 Provider–Flow 验证，保留查询与验证引用；不执行导入。返工修复指出的问题及关联实体、目标量和文字说明，再提交完整产物，避免只改 JSON 或只改说明。

LCI 目录由你直接写在正式位置，定稿并做完最后一次 provider 验证后用 `submit("LCI")` 原位验收（含交换单位与 provider 参考单位组一致性）；mapping 用 `submit("process-mapping", data=...)` 或对大文件用 `submit("process-mapping", path=workspace/outputs/...)`（也可 `path` 指向正式路径仅重新验收），正式路径只由 spec_mcp 写入。查询结果带 `project_scope`：`background` 是背景库数据，可作 provider；`uncategorized`（无分类，多为历史运行或自动连接残留的 Process/ProductSystem）和非本 run LCI 的 `project` 实体都**不能**当作 provider 证据，也不要读它们的模型图来佐证选择。provider 证据只来自背景库数据的 `validate_providers_batch` 核实结果与本 run LCI 里的前景过程。本轮最后一动作为 spec_mcp 的 `submit_handoff` 交卷。提交 `role=executor` 的 handoff，artifacts 列出 mapping 与 LCI（含 human_readable_mapping.md）。无法解决的关键数据或工具缺口明确失败，不以无依据代理补齐。
