# 06 Whole-LCA openLCA 导入与读回规范

## 1. 进入条件与产物

只有第 05 阶段预检成功并保存当前预检哈希及完整范围后才能调用 `import_lci`。本阶段必须在 `workspace/outputs/reports/` 保存：

- `import_report.json`；
- 超时恢复时的 `workspace/memory/import-operations/<preflight-hash>.json`；
- `model_graph/<product-system-slug>.json`。

文件分别遵守 `harness/specs/06-openlca-import-readback/references/schemas/import-report.schema.json` 和 `harness/specs/06-openlca-import-readback/references/schemas/model-graph.schema.json`。`product-system-slug` 使用小写字母、数字和连字符，不使用 UUID 替代可读名称。

## 2. 导入验收

- `import_report.json` 必须记录 operation ID、活动数据库、目标分类、预检哈希、创建/更新/删除范围、成功/失败计数、实体 UUID、逐项错误和耗时。
- `failed_count` 必须为 0，且每个预检中的待导入实体都有成功记录；部分成功视为 `failed`，不得继续声称运行完成。
- 重复执行仍须经过新预检；不得把历史哈希复用于变化后的范围。
- MCP 超时后必须先调用 `get_import_operation`。状态为 `running` 或 `indeterminate` 时禁止盲目重试，也不得调用 legacy CLI 绕过哈希；只有结构化最终报告可以作为阶段证据。
- `import_report.preflight_hash` 必须与 Stage 05 及 manifest 完全一致，且报告生成时间不得晚于已标记通过的 Stage 06 记录。

## 3. 模型图读回

- 导入后必须从活动数据库读回 Product System 模型图，传入 LCI 声明的 `expectedProcessIds`，记录节点、边、图指纹、`broken_links`、`disconnected_nodes` 和 `missing_expected_nodes`。
- Product System 必须由 `auto + preferDefaultProviders` 创建；`processLinks` 只接受 openLCA 创建后的读回结果，不得把 LCI 中的名义 `processLinks` 当作已建立连接的证据。
- 无法识别 Product System、节点为空、读回失败、断链、断连节点或预期节点缺失时不得进入第 07 阶段。
- 比较情景声明了不同前景过程但图指纹相同时视为 Major 建模错误；不得继续以相同拓扑执行情景比较。
- 只有导入零失败，且模型图状态为 `success`、节点非空、无断链、无断连节点时，才允许进入 LCIA 计算。
