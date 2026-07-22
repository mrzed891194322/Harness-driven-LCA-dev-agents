# Whole-LCA 导入与 LCIA 结果规范

## 1. 必需产物

每次进入写入/计算阶段的运行必须在 `workspace/results/<run_id>/` 保存：

- `import_report.json`；
- `model_graph/<product-system-slug>.json`；
- `raw/<product-system-slug>.json`；
- `calculation_manifest.json`；
- `lca_report.md`。

文件分别遵守本目录的 import report、model graph、raw LCIA results、calculation manifest schema 和 `templates/lca_report.md`。`product-system-slug` 使用小写字母、数字和连字符，不使用 UUID 替代可读名称。

## 2. 导入验收

- `import_report.json` 必须记录 operation ID、活动数据库、目标分类、预检哈希、创建/更新/删除范围、成功/失败计数、实体 UUID、逐项错误和耗时。
- `failed_count` 必须为 0，且每个预检中的待导入实体都有成功记录；部分成功视为 `failed`，不得继续声称运行完成。
- 重复执行仍须经过新预检与确认；不得把历史确认复用于变化后的范围。

## 3. 模型图与计算验收

- 模型图必须带 Product System 名称/UUID、节点、边、`broken_links` 和状态。
- `broken_links` 非空或无法识别 Product System 时，不得进入 `completed`。
- 原始 LCIA 结果必须记录方法及每个影响类别的名称、UUID、数值和单位；类别列表为空视为计算失败。
- 计算句柄必须在成功和异常路径都释放；`resource_released` 不是 `true` 时视为失败并保存证据。

## 4. Calculation manifest

`calculation_manifest.json` 必须记录活动数据库、Product System 和 LCIA 方法名称/UUID、功能单位数量、分配设置、区域化/成本设置、参数重定义、工具版本、计算时间、原始结果路径与 SHA-256、资源释放状态和总体状态。

## 5. 报告边界

`lca_report.md` 只能陈述原始结果支持的影响类别数值、方法、单位、系统边界、数据来源、限制和未解决项。不得自动宣称：

- ISO 认证或符合性认证；
- 关键审查已经通过；
- 面向公众的比较断言成立；
- 某方案具有统计或环境优势，而原始结果与方法并未支持该结论。

报告中的每个核心数值必须能回链到 raw 文件中的类别 UUID，并注明 raw 文件 SHA-256。

## 6. 评估契约联动

本文件中的必需结果、schema、模板、文件名或语义发生变化时，必须同步更新 `harness/specs/lca-quality-evaluation/references/rubric.json` 的 `artifact_coverage` 和受影响检查项，并更新质量评估契约测试。该要求是开发变更门禁，不表示 whole-lca 会自动运行质量评估。
