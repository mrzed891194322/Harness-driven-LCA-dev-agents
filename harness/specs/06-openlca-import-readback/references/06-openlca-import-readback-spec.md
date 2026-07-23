# 06 Whole-LCA openLCA 导入与读回规范

## 1. 进入条件与产物

只有第 05 阶段预检成功并保存当前预检哈希及完整范围后才能调用 `import_lci`。本阶段必须在 `workspace/outputs/reports/` 保存：

- `import_report.json`；
- `model_graph/<product-system-slug>.json`。

文件分别遵守 `harness/specs/public/references/schemas/import-report.schema.json` 和 `harness/specs/public/references/schemas/model-graph.schema.json`。`product-system-slug` 使用小写字母、数字和连字符，不使用 UUID 替代可读名称。

## 2. 导入验收

- `import_report.json` 必须记录 operation ID、活动数据库、目标分类、预检哈希、创建/更新/删除范围、成功/失败计数、实体 UUID、逐项错误和耗时。
- `failed_count` 必须为 0，且每个预检中的待导入实体都有成功记录；部分成功视为 `failed`，不得继续声称运行完成。
- 重复执行仍须经过新预检；不得把历史哈希复用于变化后的范围。

## 3. 模型图读回

- 导入后必须从活动数据库读回 Product System 模型图，记录名称/UUID、节点、边、`broken_links` 和状态。
- 无法识别 Product System、节点为空、读回失败、`broken_links` 非空或 `disconnected_nodes` 非空时不得进入第 07 阶段；保存证据并置为 `failed`。
- 只有导入零失败，且模型图状态为 `success`、节点非空、无断链、无断连节点时，才允许进入 LCIA 计算。
