# 02 前景清单审查（eval-reviewer）

产物字段见 `harness/specs/02-inventory-extraction/`。本文件只写审查口径。

- 计划范围内的物料/工序是否都有 BOM 行。
- 数值能否回链到 `harness/knowledge/` 原文（路径 + 页或章节）。
- 未读文件是否诚实标记为 `unreadable`，不得把编造数量当成通过。
- 本阶段不应出现 openLCA 查询或 LCI 写入；若产物依赖查库则 `failed`。
