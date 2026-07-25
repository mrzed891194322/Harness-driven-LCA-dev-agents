# 03 Whole-LCA LCI 制定规范

## 1. 输入

- 输入必须包含已通过的执行计划、第 01 阶段审查结果和第 02 阶段的可追踪检索证据。
- 所有引用的输入产物必须记录 artifact ID、路径和 SHA-256；不得使用未记录的口头结论替代证据。

## 2. 制定约束

- LCI 创建或修正由专用执行 Agent 完成，产物写入 `workspace/outputs/LCI/`。
- 只允许 `flows/`、`processes/`、`product_systems/` 三个实体目录；每个 JSON 文件只能包含一个与目录匹配的 openLCA JSON-LD 实体。根目录或嵌套目录中的 JSON、聚合容器和辅助报告均不属于可导入 LCI。
- 每个实体必须包含固定 `@context`、合法 `@type`、非空 `@id` 和 `name`。映射报告固定为 `workspace/outputs/LCI/human_readable_mapping.md`；机器报告写入 `workspace/outputs/reports/`。
- 比较情景必须使用 `linkingMode: explicit` 声明 `processes`、`processLinks` 和 `expectedProcessIds`，使每个情景的预期前景过程可被导入后读回验证。非比较性单一系统可使用 `linkingMode: auto`。
- 数值、单位、Provider、UUID 和系统边界必须能回链到计划或第 02 阶段证据；不得猜测缺失事实。
- 映射报告中的每个换算公式必须写明输入和输出单位及换算因子；例如质量以 kg、运输工作以 t*km 时必须显式记录 kg→tonne 的 `/1000`。
- 背景 Provider 必须使用正式查询得到的 UUID，并输出 exchange 引用的 flow。`expectedProviderGeography` 可记录计划中的地域文本，但只作可追踪诊断；openLCA 的地域代码、名称或别名不一致不得覆盖 UUID 与输出 flow 的一致性判断。
- 初次制定不得提前执行 openLCA 写入；本阶段只形成可审查的 LCI 材料。

## 3. 输出与完成条件

- 阶段交接必须列出全部 LCI 产物及 SHA-256、来源 artifact ID、所用证据、未解决项和下一动作。
- 进入第 04 阶段前必须运行 `references/scripts/validation.py`；只有 Flow、Process、Product System 均非空、校验返回 `ok=true` 且无阻断性证据缺口时才能继续。
- 本阶段完成不表示 LCI 已通过质量评估，也不允许跳过第 04 阶段进入预检。
