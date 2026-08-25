# 02 Whole-LCA 证据检索规范

## 1. 输入与任务提取

- 仅接收第 01 阶段已通过的执行计划和计划审查。用户计划不要求出现 `GAP-*` 字面量。
- 检索任务来自计划中的自然语言说明、审查里的 `retrievable_gaps`，以及建立前景 LCI 所需的背景 Process、Flow、Provider、LCIA 方法和数据库实体映射。即使 `retrievable_gaps` 为空，只要审查为 `passed`，仍进入本阶段并执行计划所隐含的资料提取与背景匹配。
- 检索不得改变计划中的目标、功能单位、系统边界、截断或分配等用户价值判断。

## 2. 来源与回读

用户资料与方法纪律见 `harness/rules/lca-knowledge/README.md`，openLCA 调用纪律见 `harness/rules/openlca-operation/README.md`。本阶段 additionally 要求：

- 检索范围必须服从每个缺口声明的来源域，只能使用 `harness/knowledge/` 中的用户文件、活动 openLCA 数据库或二者。
- 用于决策的关键事实必须读取原文，并记录来源文件、章节或页码。禁止调用 `query_rag`。
- openLCA 候选必须记录实体类型、名称、UUID、活动数据库、查询词、查询时间和选择理由。候选 Process 的地域和定量参考用 `get_process_details` 按 UUID 回读；背景 Provider 映射先查询 Flow UUID，再用 `get_flow_providers` 回读可用 Provider。不得为这些选择批量导出完整 Process 实体集合。
- 背景匹配与无人值守决定遵守已加载或按需读取的 `harness/rules/openlca-operation/README.md`：可留档的选择自行决定并写入证据，不得停下来征求用户。

## 3. 交接证据

检索交接必须遵守 `harness/specs/public/references/schemas/handoff.schema.json`，并记录查询词、候选项、选择理由、原文位置或数据库实体 UUID、未解决项和关联 issue ID。

每项检索任务必须明确标记为已解决或未解决。已按 openLCA 规则记录 UUID 的匹配决定不算未解决项。同类活动完全不存在、或缺口属于计划第 01 阶段阻断性事实时，均将运行置为 `failed`，并在 `status_reason` 写明具体原因。只有阻断检索均有可追踪证据（含已记录的匹配决定）时才能进入第 03 阶段。
