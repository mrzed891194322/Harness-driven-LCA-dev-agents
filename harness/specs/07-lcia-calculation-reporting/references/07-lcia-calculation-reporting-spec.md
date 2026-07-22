# 07 Whole-LCA LCIA 计算与报告规范

## 1. 必需产物

本阶段必须在 `workspace/results/<run_id>/` 保存：

- `raw/<product-system-slug>.json`；
- `calculation_manifest.json`；
- `lca_report.md`。

原始结果和计算清单分别遵守 `harness/specs/public/references/schemas/raw-lcia-results.schema.json` 与 `harness/specs/public/references/schemas/calculation-manifest.schema.json`；报告遵守 `harness/specs/public/references/templates/lca_report.md`。

## 2. 计算验收

- 原始 LCIA 结果必须记录方法及每个影响类别的名称、UUID、数值和单位；类别列表为空视为计算失败。
- 计算句柄必须在成功和异常路径都释放；`resource_released` 不是 `true` 时视为失败并保存证据。
- `calculation_manifest.json` 必须记录活动数据库、Product System 和 LCIA 方法名称/UUID、功能单位数量、分配设置、区域化/成本设置、参数重定义、工具版本、计算时间、原始结果路径与 SHA-256、资源释放状态和总体状态。

## 3. 报告边界

`lca_report.md` 只能陈述原始结果支持的影响类别数值、方法、单位、系统边界、数据来源、限制和未解决项。不得自动宣称：

- ISO 认证或符合性认证；
- 关键审查已经通过；
- 面向公众的比较断言成立；
- 某方案具有统计或环境优势，而原始结果与方法并未支持该结论。

报告中的每个核心数值必须能回链到 raw 文件中的类别 UUID，并注明 raw 文件 SHA-256。

## 4. 最终完成门禁

只有导入无失败、模型图无断链、LCIA 原始结果非空、计算资源已释放，且第 06、07 阶段全部必需文件通过 schema 和模板验收时，manifest 才能置为 `completed`。

本阶段的必需结果、schema、模板、文件名或语义发生变化时，必须同步更新 LCA 质量评估的固定产物覆盖矩阵、受影响检查项和契约测试。该要求是开发变更门禁，不表示 whole-lca 会自动运行质量评估。
