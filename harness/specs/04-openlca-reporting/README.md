---
id: 04-openlca-reporting
inputs:
  - workspace/outputs/LCI/
  - workspace/outputs/inventory/extracted-bom.json
  - workspace/outputs/inventory/process-mapping.json
outputs:
  - workspace/outputs/reports/lca_report.md
---

# 04 openLCA 建模与报告

导入 LCI、计算并写出最终报告。

报告提纲：`references/templates/lca_report.md`

## 输入

- `workspace/outputs/LCI/`
- `workspace/outputs/inventory/extracted-bom.json`
- `workspace/outputs/inventory/process-mapping.json`

## 产物

- `workspace/outputs/reports/lca_report.md`
- 工具原始返回落在 `workspace/outputs/reports/`

## 验收

报告文件存在、可读；数值能指到 raw；限制节包含留档决定；前景清单与映射节能指回 BOM `item_id`。空结果或工具失败不得当作完成。
