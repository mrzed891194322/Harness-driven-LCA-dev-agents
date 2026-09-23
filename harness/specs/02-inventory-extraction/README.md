---
id: 02-inventory-extraction
inputs:
  - workspace/inputs/plan.md
---

# 02 前景清单提取

从声明资料提取可追溯 BOM 及建模所需的数量依据。本阶段不查询 openLCA、不写 LCI；执行后审查，最多 3 轮。

## 输入

已通过的计划及本任务 `source_manifest` / `knowledge_sources` 声明的资料。按来源规则读取；受限离线脚本可以辅助提取和换算，无法读取的资料如实记录。

## 提交

- `workspace/outputs/inventory/extracted-bom.json`：权威结构化清单，GUI 读取。
- `workspace/outputs/inventory/extracted-bom.md`：同一批行的表格与方法说明，供后续建模和审查。

JSON 保持 `items` 数组，每行仍为：item_id（本运行稳定）、name、quantity、unit、process、transport（方式/距离，未知可空）、geography、source_locations、extraction_status（extracted / partial / unreadable）及可选缺口说明。未知 quantity 可为 null，extracted 行必须有数量，不新增状态枚举。示例见 `references/examples/extracted-bom.json`。

Markdown 在清单表后提交：

1. **需求与情景清单**：计划/修订位置、要求、必做或可选、适用情景、对应 item_id 或后续阶段交付。覆盖全部要求，不能只列已有数据的情景。
2. **数量基准与推导**：各情景的功能单位，源数值与单位、单件/批量基准、公式及系数依据，定位到 item_id；共同公式可合并说明，不能丢失对应关系。
3. **范围与缺口**：各环节物料、能源、水、运输、排放、废物的已覆盖项，以及未知、计划允许排除、不适用项；记录估算/代理依据、未读文件和资料冲突的处理。汇总可做的平衡与数量级核对。

## 验收

- 研究范围和全部必做情景有可核查的清单覆盖；“后续交付”必须能辨认其输入依据，不能作为漏提清单的理由。
- 数值可回链原文或有依据的推导，JSON 与 Markdown 一致，数量基准与量纲正确；已知零、未知和排除不混淆。
- 不存在未经授权排除或无依据补齐的关键缺口；工序列名不能冒充负荷已覆盖。阶段 03 才能决定的背景匹配留档交接，不在本阶段查库。
- reviewer 按清单规则独立核对；缺少产物、执行失败或 blocked 不得视为完成。

## 机器检查与返工

主编排在写者合法 ok 且产物齐全后运行 inventory 检查，失败返工；reviewer 再判断方法与证据。写者可选提前调用同一 profile，但不必自行检查后才提交。详细状态与引用协议见公共契约；机器检查不证明 Markdown 的需求覆盖和推导正确。第 3 次仍未通过则 failed。
