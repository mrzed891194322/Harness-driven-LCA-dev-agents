---
id: 02-inventory-extraction
inputs:
  - workspace/inputs/plan.md
  - harness/knowledge/
outputs:
  - workspace/outputs/inventory/extracted-bom.json
  - workspace/outputs/inventory/extracted-bom.md
---

# 02 前景清单提取

从用户资料抽出前景 BOM。权威产物是 JSON（工作细节面板渲染它）。

示例：`references/examples/extracted-bom.json`

## 输入

- `workspace/inputs/plan.md`
- `harness/knowledge/`

## 产物

- `workspace/outputs/inventory/extracted-bom.json`
- `workspace/outputs/inventory/extracted-bom.md`

每行至少含：`item_id`、`name`、`quantity`、`unit`、`process`、`transport`、`geography`、`source_locations`、`extraction_status`（`extracted` | `partial` | `unreadable`）、缺口说明（可空）。

## 验收

产物文件存在。计划范围内的物料/工序有行；读得出的数值能回链原文；读不出的标 `unreadable`，不得编造数量。
