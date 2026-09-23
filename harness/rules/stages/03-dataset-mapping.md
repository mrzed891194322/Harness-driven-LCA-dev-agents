# 03 背景数据集映射与前景建模

为 BOM 中需要建模的活动选择背景数据并建立可导入 LCI，完成所有需要改变模型的必做情景。执行后审查，最多 3 轮；本阶段禁止导入。

## 方法

遵守共同方法、清单、映射与工具规则。mapping JSON 的 items 每行对应 BOM item_id，包含选用 Flow / Process / Provider 的名称与 UUID、请求/实际地域、中文 selection_reason 和候选摘要。每个 BOM item_id 仍有且仅有一条映射；一条行涉及多个情景或 exchange 的对应关系写在 Markdown，不用复制 item_id 破坏覆盖关系。

新建前景实体的名称和 UUID 明确标为本次创建；背景实体须正式查询。仅作范围记录或计划已允许排除的行，在 selection_reason 明说“不计入模型”及依据，不适用的实体字段可留空，不虚构 Provider。实际计入聚合过程的行须指出负荷承接关系。

LCI 保持 flows/、processes/、product_systems/ 中一文件一实体的 JSON-LD，以及根目录 `human_readable_mapping.md`。

JSON-LD 保持现有导入契约：exchange 显式布尔 isInput；每个 Process 恰好一个输出 isQuantitativeReference=true；需要供应过程的前景输入给 defaultProvider；Product System 使用 linkingMode=auto、preferDefaultProviders=true，不用 processLinks 预置待导入拓扑，不使用 input / quantitativeReference 别名。无法用当前导入契约表达的必做模型如实报告能力缺口，不改工具绕过。

`human_readable_mapping.md` 必须包含：

1. **情景与需求对应**：每个必做情景的 Product System、参考过程/流、本次创建的实体及其对应要求。不同模型情景用不同 Product System；灵敏度所需的模型变体也在本阶段建好并审核。
2. **数量换算链**：源数据和 BOM item_id → exchange 数量/单位 → 定量参考输出 → 实现功能单位所需的参考流数量/单位 → 04 应使用的 amount。同步 JSON-LD、mapping 描述及此说明，不能只改一处目标量。
3. **适配与覆盖**：候选查询证据、选用依据和代表性缺口；聚合/背景活动、计划允许排除项和未解决项；市场与显式运输、原料与加工、聚合与分步过程、回收信用的重复计算核查及依据。

示例 UUID 仅展示结构，不能当作查询结果。

## 验收

- 每个 BOM item_id 的处理可追溯，功能适配、代表性、负荷覆盖和排除有依据，无关键未解决的错配或重复计算。
- 所有必做模型情景齐全；数量换算链完整、可复算且与实际实体一致，不能把 targetAmount 文字当作计算依据的全部。
- 背景实体有正式证据，新建前景 UUID 稳定一致；Provider–Flow 关系验证针对最终模型，后续修改后刷新失效证据。
- 未导入；需要修改上游 BOM/计划时停止并交回上游审查，不在本阶段静默改已审输入。

## 机器检查与返工

主编排在写者合法 ok 且产物齐全后运行 mapping 检查，失败返工，再由 reviewer 独立判断方法。检查证明结构、覆盖及已有 Provider 证据，不证明功能单位、换算、功能等价和需求落实。第 3 次仍未通过则 failed。
