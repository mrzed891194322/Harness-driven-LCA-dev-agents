# 04 报告审查

按本阶段共有契约审查最终报告，不修改被审文件，不重跑导入。

## 证据核对

- 最终报告是否可读，面向用户的说明是否为中文。
- 数值能否指到 `workspace/outputs/reports/` 中的 MCP 原始返回。
- 限制节是否包含地域代理等留档决定。
- 前景清单与数据集映射两节能否指回 BOM `item_id`。
- 工具报错、空结果或资源未释放不得标为通过。

## 复审

必须重新读取最新 `lca_report.md`，刷新校验状态并核对当前采用的 raw 校验和；先读变化项和 failed/stale 检查，再按需抽查原始证据。核实原问题是否解决及修改是否引入新问题，不一次展开全部 raw。历史对话中的报告和旧结论不能替代本轮核对。

## 返工意见

`fix_instructions` 定位到报告章节、缺失的原始文件或 BOM `item_id`。

## 提交

handoff：`status` 为 `passed` 或 `failed`。通过则本工作流可结束为 `completed`。

使用本阶段绑定的 lca_artifacts：`get_validation_state("report")` 查看状态，`validate_artifacts("report")` 核对最新证据。只引用工具生成的检查，不自报权威校验计数。
