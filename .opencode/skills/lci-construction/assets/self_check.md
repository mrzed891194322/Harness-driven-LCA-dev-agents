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
