---
id: 02-inventory-extraction
inputs:
  - workspace/inputs/plan.md
  - harness/knowledge/
---

# 02 前景清单提取

从用户资料抽出标准化 BOM。权威产物是 `extracted-bom.json`（工作细节面板渲染它）。本阶段不查询 openLCA、不写 LCI。执行后审查，最多 3 轮。

## 阶段目标

把计划范围内的物料、工序与运输等前景流写成可追溯的 BOM 行。

## 输入说明

已通过的 `workspace/inputs/plan.md`，以及 `harness/knowledge/` 中的文件（图纸、合同、ERP 导出、PDF 等）。直接读文件。读得出的文本/表格必须抽取并记下位置；读不出的二进制标为 `unreadable`，不得编造数量。

## 提交要求

- `workspace/outputs/inventory/extracted-bom.json`
- `workspace/outputs/inventory/extracted-bom.md`（同一批行的表格；审查/落盘用，GUI 不读）

每行字段：

- `item_id`：本运行内稳定
- `name`：名称/规格
- `quantity`、`unit`
- `process`：工序或生命周期环节
- `transport`：方式/距离，未知则空
- `geography`
- `source_locations`：可定位引用（文件路径 + 页或章节；若来自已注册检索工具，可用远程文档 ID 或片段位置）
- `extraction_status`：`extracted` | `partial` | `unreadable`
- 缺口说明（可空）

示例：`references/examples/extracted-bom.json`。

## 验收标准

- 计划范围内的物料/工序都有 BOM 行。
- 数值能回链到资料原文（路径 + 页或章节，或其他可定位引用）。
- 未读文件诚实标记为 `unreadable`，不得把编造数量当成通过。
- 产物不依赖 openLCA 查询。

## 前置及停止条件

第 3 次审查仍失败则运行 `failed`。执行失败、缺少产物或 `blocked` 不得当作完成。

## 机器证据

写者提交前不必调用 `validate_artifacts`。主编排在合法 `ok` 且产物齐全后运行 `profile="inventory"` 检查；失败则返工写者。handoff 可引用 checks_ref.path 和 evidence_manifest_ref。reviewer 独立核对证据并决定通过，不把工具成功当作阶段通过。检查定义见公共 `references/evidence-contract.md`；旧检查输入变化即 stale。
