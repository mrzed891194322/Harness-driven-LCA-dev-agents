# LCI 交付验收与自检规范

本文件规定 LCI 构建结果必须满足的交付物、目录结构、证据要求、结构自检与导入前验收条件。执行步骤不在本文件中定义。

## 1. 必须交付的文件

所有 LCI 构建产物必须集中放置于 `workspace/LCI/`。

- `workspace/LCI/flows/`：Flow JSON 文件。
- `workspace/LCI/processes/`：Process JSON 文件。
- `workspace/LCI/product_systems/`：Product System JSON 文件。
- `workspace/LCI/human_readable_mapping.md`：人类可读映射报告。

若某类实体确无产物，必须在映射报告中说明原因；不得默默缺省。

## 2. 目录与命名验收

- Flow 文件名必须采用 `f<两位数编号>-<英文具体名称（小写，连字符分隔）>.json`。
- Process 文件名必须采用 `p<编号>-<英文具体名称（小写，连字符分隔）>.json`。
- Product System 文件名必须采用 `ps<编号>-<英文具体名称（小写，连字符分隔）>.json`。
- JSON 内部 `name` 必须与文件编号一致：
  - Flow：`F + 两位数编号 + 空格 + 具体名称`
  - Process：`P + 编号 + 空格 + 具体名称`
  - Product System：`PS + 编号 + 空格 + 具体名称`
- 其他 Process 文件的 `exchanges` 列表引用 Flow 时，`flow.name` 必须与 Flow 文件内部 `name` 完全一致。

## 3. JSON-LD 与 UUID 自检

- 所有 JSON 必须是有效 JSON，字段命名必须采用 openLCA JSON-LD 需要的 camelCase。
- 每个实体必须包含合法且唯一的 `@id` UUID。
- 每个实体和内嵌引用对象必须包含正确的 `@type`。
- Process 中每个 `exchange.flow.@id` 必须能匹配到已生成或明确引用的 Flow。
- 不允许存在悬空 UUID、伪造 UUID 或无法解释的引用。
- 涉及常用质量/千克单位时，必须使用 `mapping_spec.md` 中给出的官方 UUID，不得自行捏造单位或流属性 UUID。

## 4. Process Exchange 自检

- 每个 Process 必须有且仅有一个核心输出交换设置 `"isQuantitativeReference": true`。
- 输入交换的 `isInput` 必须为 `true`。
- 输出、产品、排放或废弃物流的 `isInput` 必须为 `false`。
- 所有 `amount` 必须是有效数值，不得使用字符串占位或无法计算的表达式。

## 5. Provider Linking 自检

- 所有输入交换必须包含 `defaultProvider`。
- `defaultProvider` 必须包含 `@type: "Process"` 及正确的 `@id`。
- 内部前台过程链接必须指向系统内真实存在且负责产出该 Flow 的 Process。
- 外部背景数据链接必须来自正式工具查询结果，并在映射报告中记录查询来源或证据。
- 下游输入 Flow ID 必须与上游提供方 Process 的对应输出 Flow ID 完全一致。
- 不允许存在孤立输入流、悬空 Provider、伪造 Provider 或无法解释的数据集连接。

## 6. 人类可读映射报告自检

`workspace/LCI/human_readable_mapping.md` 必须严格遵守 `harness/specs/lci-construction/references/templates/human_readable_mapping.md`。

- 文件开头必须保留 YAML front matter：
  - `template_kind: lci_human_readable_mapping`
  - `template_version: "1"`
- 正文必须保留模板规定的一级/二级标题、核心表格、Mermaid 代码块与“人类审核提示”章节。
- 至少包含“映射概述”“系统边界与核心过程”“核心物质流”“产品系统配置”“过程拓扑依赖关系”和“人类审核提示”。
- 表格、Mermaid 代码块、来源追溯、假设、不确定项和人类审核提示必须填充为真实内容，不得保留明显占位符。
- Mermaid 图表必须可被 GUI Markdown 页面渲染；含括号、化学式或特殊符号的连接标签必须使用双引号。
- 如果报告缺少模板元数据、章节缺失、章节顺序错乱、仍包含明显占位符，或 Markdown 结构无法被 GUI 渲染，必须判定为未通过并要求返回修正。

## 7. 导入验收

- 导入前必须通过本文件全部自检项。
- 导入命令、参数、openLCA IPC 连接信息和导入结果必须可追溯。
- 导入后必须记录 Flow、Process、Product System 的导入数量及成功/失败状态。
- 如导入失败，必须保留失败原因并返回修正；不得宣称交付完成。
