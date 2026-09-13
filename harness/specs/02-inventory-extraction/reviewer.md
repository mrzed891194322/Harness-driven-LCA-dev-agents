# 02 前景清单审查

按本阶段共有契约独立核对 BOM，不修改被审文件。

## 证据核对

- 计划范围内的物料/工序是否都有 BOM 行。
- 数值能否回链到资料原文（路径 + 页或章节，或其他可定位引用）。
- 未读文件是否诚实标记为 `unreadable`，不得把编造数量当成通过。
- 本阶段不应出现 openLCA 查询或 LCI 写入；若产物依赖查库则 `failed`。

## 复审

在原评估会话中复审时必须重新读取最新 `extracted-bom.json` / `.md`，核实原问题是否解决，并检查修改是否引入新问题。历史对话中的产物内容和旧结论不能替代本轮核对。

## 返工意见

失败时 `fix_instructions` 定位到具体 `item_id` 或缺失资料，说明要改什么。

## 提交

handoff：`status` 为 `passed` 或 `failed`，`status_reason` 非空。

使用本阶段绑定的 lca_artifacts：`get_validation_state("inventory")` 查看状态，`validate_artifacts("inventory")` 核对最新证据。只引用工具生成的检查，不自报权威校验计数。
