# 06 Whole-LCA openLCA 导入与读回规范

## 1. 进入条件与产物

只有第 05 阶段预检成功并保存当前 `import_scope` 后才能调用 `import_lci`。本阶段必须在 `workspace/outputs/reports/` 保存：

- `import_report.json`；
- 超时恢复时的 `workspace/memory/import-operations/current.json`；
- `model_graph/<product-system-slug>.json`。

文件分别遵守 `harness/specs/06-openlca-import-readback/references/schemas/import-report.schema.json` 和 `harness/specs/06-openlca-import-readback/references/schemas/model-graph.schema.json`。`product-system-slug` 使用小写字母、数字和连字符，不使用 UUID 替代可读名称。

## 2. 导入验收

导入与超时恢复的通用纪律见 `harness/rules/openlca-operation/README.md`。本阶段 additionally 要求：

- `import_report.json` 必须记录 operation ID、活动数据库、目标分类、LCI 目录、创建/更新/删除范围、成功/失败计数、实体 UUID、逐项错误和耗时。
- `failed_count` 必须为 0，且每个预检中的待导入实体都有成功记录；部分成功视为 `failed`，不得继续声称运行完成。
- 调用 `import_lci` 时传入与第 05 阶段相同的库名、分类和 LCI 目录；工具内部核对范围，Agent 不抄写哈希。
- `import_report` 的库名、分类、LCI 目录必须与 Stage 05 及 manifest `import_scope` 一致，且报告生成时间不得晚于已标记通过的 Stage 06 记录。

## 3. 模型图读回

- 导入后必须从活动数据库读回 Product System 模型图，传入 LCI 声明的 `expectedProcessIds`，记录节点、边、`broken_links`、`disconnected_nodes` 和 `missing_expected_nodes`。
- Product System 必须由 `auto + preferDefaultProviders` 创建；`processLinks` 只接受 openLCA 创建后的读回结果，不得把 LCI 中的名义 `processLinks` 当作已建立连接的证据。
- 无法识别 Product System、节点为空、读回失败、断链、断连节点或预期节点缺失时不得进入第 07 阶段。
- 只有导入零失败，且模型图状态为 `success`、节点非空、无断链、无断连节点时，才允许进入 LCIA 计算。
