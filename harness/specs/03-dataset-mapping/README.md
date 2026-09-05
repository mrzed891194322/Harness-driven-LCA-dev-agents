---
id: 03-dataset-mapping
inputs:
  - workspace/outputs/inventory/extracted-bom.json
  - workspace/inputs/plan.md
outputs:
  - workspace/outputs/inventory/process-mapping.json
  - workspace/outputs/LCI/human_readable_mapping.md
---

# 03 背景数据集映射

把 BOM 行映射到活动库并写出可导入 LCI。工作细节面板渲染 `process-mapping.json`。

示例：`references/examples/process-mapping.json`

## 输入

- `workspace/outputs/inventory/extracted-bom.json`
- `workspace/inputs/plan.md`

## 产物

- `workspace/outputs/inventory/process-mapping.json`（每行：`item_id`、选用 Flow/Process/Provider 的名称与 UUID、请求/实际地域、`selection_reason`）
- `workspace/outputs/LCI/`：`flows/`、`processes/`、`product_systems/` 的 JSON-LD，以及根目录 `human_readable_mapping.md`

## 验收

产物文件存在。映射功能对应、理由写清、LCI 能对上 BOM `item_id`。名称与 UUID 须来自正式查询，禁止编造。
