# LCI 生成质量自检规范 (Self-Check Specification)

本文件专为自检 Agent 或生成后校对模块使用，用于严格检查生成的 LCI JSON 结构是否符合要求，以保证导入 openLCA 的高成功率。

## 自检核心清单

在将所有 JSON 配置文件输出前，请发挥 LLM 的自我纠错和推理验证能力，逐项执行以下自检操作：

1. **UUID 的唯一性与交叉引用匹配**
   - 检查每一个实体（Flow, Process）是否都被分配了合法格式的全局唯一 UUID (`@id`)。
   - **引用匹配核对**：遍历每一个 Process 内部的 `exchanges` 列表，检查其中引用的 `flow` 下的 `@id`，是否**完全等于**（一一对应）已生成的 Flow 实体自身的 UUID。任何悬空的（无对应 Flow 的）UUID 或伪造的 UUID 都必须被拦截并修复。

2. **基准产出 (Quantitative Reference) 验证**
   - 检查每一个 Process。
   - 确认其 `exchanges` 中，是否有且仅有一个输出流（或者主产品流）包含了 `"isQuantitativeReference": true` 的标记。若缺失此标记，openLCA 无法创建关联的产品系统。

3. **方向标记 (isInput) 与金额 (amount) 验证**
   - 确认所有的输入（原料、能源）其 `isInput` 设为 `true`。
   - 确认所有的产出（产品、排放、废弃物）其 `isInput` 设为 `false`。
   - 确认所有的 `amount` 都为有效的浮点数类型。

4. **预设单位关联的准确性**
   - 检查是否遵循了官方强制的常用 UUID（如涉及千克/质量，必须使用 `20a8dd24...` 和 `bca7e4ea...` 等）。不要出现自行捏造单位 UUID 的情况。

5. **JSON-LD Schema 合规**
   - 确认所有生成的文件内容为有效的、严格遵循 **camelCase** 命名法的 JSON。
   - 顶层级以及内嵌 `Ref` 对象中，是否遗漏了 `@type` 标记。

6. **提供者链接 (Provider Linking) 完整性**
   - 遍历每一个 Process 内部的 `exchanges` 列表。
   - 【关键项】确认所有 `isInput: true` 的输入流中，是否都**明确且正确地包含**了 `defaultProvider` 字段（需包含 `@type: "Process"` 及正确的 `@id`）。
   - **输入输出 Flow ID 严格一致性校验**：必须验证每个 `defaultProvider` 指向的提供方 Process 的 JSON 文件，确认该提供方 Process 的输出交换（`isInput: false`）中，**必定存在一个输出流的 `@id` 与当前接收方的输入流 `@id` 完全一致**。严禁出现“下游输入流 ID 与上游输出流 ID 不匹配”的断裂情况（例如：下游 P9 消耗中间件 Flow-A 并指定上游 P7 为 Provider，但上游 P7 仅输出成品 Flow-B，这会导致 openLCA 因 ID 不匹配而无法连线）。
   - 核实内部工序链接的 `defaultProvider` ID 是否真实指向了系统内负责产出该流的其他 Process；外部背景数据链接的 ID 是否通过工具查询获得。任何孤立的、无来源的输入流都必须被指出并修复，否则无法生成模型图。

7. **Mermaid 图表语法规范校验**
   - 检查报告中若包含 Mermaid 图表（如系统依赖/拓扑关系图），必须逐行检查连接线上的标签文本（例如 `A -->|label| B`）。
   - 如果标签包含 `()`、`[]`、`{}` 等括弧符号，或者包含含有数字上下标的化学分子式，确认它们是否都已用双引号括起来（如 `A -->|"KAu(CN)₂ + NaCN"| B`）。如若未加双引号，必须指示修改以防渲染解析错误。

8. **命名规范校验**
   - 检查所有的 Flow、Process 以及 Product System 的文件名与内部 `"name"` 属性是否匹配且合规：
     - **Flow（流）**：文件名应采用 `f<两位数编号>-<英文具体名称（小写，连字符分隔）>.json`，且 JSON 内部的 `"name"` 属性必须采用 `F + 两位数编号 + 空格 + 具体名称` 的格式（如 `"F01 Gold-plated product"`）。同时，检查其他 Process 文件的 `exchanges` 列表中引用此 Flow 时，其 `flow` 下的 `name` 属性是否与之完全一致。
     - **Process（过程）**：文件名应采用 `p<编号>-<英文具体名称（小写，连字符分隔）>.json`，且 JSON 内部的 `"name"` 属性必须采用 `P + 编号 + 空格 + 具体名称` 的格式（如 `"P1 Chemical Degreasing"`）。
     - **Product System（产品系统）**：文件名应采用 `ps<编号>-<英文具体名称（小写，连字符分隔）>.json`，且 JSON 内部的 `"name"` 属性必须采用 `PS + 编号 + 空格 + 具体名称` 的格式（如 `"PS1 Gold Plating Product System"`）。
