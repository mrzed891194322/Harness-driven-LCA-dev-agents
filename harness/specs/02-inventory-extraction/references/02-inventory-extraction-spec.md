# 02 前景清单提取

## 谁做

主编排先委派 `sub-executor` 抽取，再委派 `eval-reviewer` 审查。最多 3 轮。本阶段不查询 openLCA、不写 LCI。

## 输入

已通过的 `workspace/inputs/plan.md`，以及 `harness/knowledge/` 中的文件（图纸、合同、ERP 导出、PDF 等）。直接读文件。读得出的文本/表格必须抽取并记下位置；读不出的二进制标为 `unreadable`，不得编造数量。

## 产物

- `workspace/outputs/inventory/extracted-bom.json`（工作细节面板渲染此文件）
- `workspace/outputs/inventory/extracted-bom.md`（同一批行的表格；审查/落盘用，GUI 不读）

每行字段：

- `item_id`：本运行内稳定
- `name`：名称/规格
- `quantity`、`unit`
- `process`：工序或生命周期环节
- `transport`：方式/距离，未知则空
- `geography`
- `source_locations`：文件路径 + 页或章节
- `extraction_status`：`extracted` | `partial` | `unreadable`
- 缺口说明（可空）

示例：`examples/extracted-bom.json`。

## 审查

Reviewer 判断：计划范围内的物料/工序是否有行、数值能否回链原文、未读文件是否诚实标记。通过则进入 03。
