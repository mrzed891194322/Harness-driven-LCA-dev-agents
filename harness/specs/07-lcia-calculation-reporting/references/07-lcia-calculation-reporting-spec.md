# 07 Whole-LCA LCIA 计算与报告规范

## 1. 必需产物

本阶段必须在 `workspace/outputs/reports/` 保存：

- `raw/<product-system-slug>.json`；
- `calculation_manifest.json`；
- `lca_report.md`。

原始结果和计算清单分别遵守 `harness/specs/07-lcia-calculation-reporting/references/schemas/raw-lcia-results.schema.json` 与 `harness/specs/07-lcia-calculation-reporting/references/schemas/calculation-manifest.schema.json`；报告遵守 `harness/specs/07-lcia-calculation-reporting/references/templates/lca_report.md`。

## 2. 计算验收

openLCA 计算与资源释放的通用纪律见 `harness/rules/openlca-operation/README.md`。本阶段 additionally 要求：

- 原始 LCIA 结果必须记录方法及每个影响类别的名称、UUID、数值和单位；类别列表为空视为计算失败。
- 计算句柄必须在成功和异常路径都释放；`resource_released` 不是 `true` 时视为失败并保存证据。
- `calculation_manifest.json` 使用 v3 `calculations` 非空数组。每个元素记录一个 Product System 的功能单位、设置、原始结果路径、资源释放和状态；共享层记录活动数据库、LCIA 方法、工具版本和总体状态。
- 多情景清单必须为每一对 Product System 生成 `comparison_checks`，记录两侧 Product System、原始 LCIA profile 是否完全相同、状态与解释。
- 单情景也必须使用一个元素的 `calculations` 数组；不得把额外情景塞入 `unresolved_items`。
- 总体 `status=success` 仅在所有 calculation 均成功、raw 非空且 `resource_released=true` 时成立。

## 3. 报告边界

`lca_report.md` 只能陈述原始结果支持的影响类别数值、方法、单位、系统边界、数据来源、限制和未解决项。不得自动宣称：

- ISO 认证或符合性认证；
- 关键审查已经通过；
- 面向公众的比较断言成立；
- 某方案具有统计或环境优势，而原始结果与方法并未支持该结论。

报告中的每个核心数值必须能回链到 raw 文件中的类别 UUID，并注明 raw 文件路径。

## 4. 最终完成门禁

生成全部结果后必须运行 `references/scripts/validation.py`。只有导入无失败、模型图包含全部预期节点、所有 LCIA 原始结果非空、计算资源已释放、每对情景 comparison check 正确，且第 06、07 阶段全部必需文件通过结构验收时，manifest 才能置为 `completed`。图不同但 LCIA 完全相同时必须记录非空解释，否则置为 `needs_review`，不得自动宣称情景等效。

本阶段的必需结果、schema、模板、文件名或语义发生变化时，必须同步更新 LCA 质量评估的固定产物覆盖矩阵、受影响检查项和契约测试。该要求是开发变更门禁，不表示 whole-lca 会自动运行质量评估。
