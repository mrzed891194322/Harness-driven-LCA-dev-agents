# 06 openLCA 导入与读回 Schema 握手映射

本文是维护索引，不替代本阶段 spec、本阶段 JSON Schema、openLCA 操作规则或 MCP 运行时 schema。

## 握手流程

```mermaid
flowchart TD
    preflight["05 范围 + preflight_hash"]
    request["导入请求 handoff"]
    executor["sub-executor"]
    import["import_lci<br/>重新预检后写入"]
    operation["get_import_operation<br/>超时状态"]
    report["import_report.json<br/>import-report.schema.json"]
    graphTool["get_model_graph"]
    graph["model_graph/slug.json<br/>model-graph.schema.json"]
    returned["导入/读回返回 handoff"]
    stage["06 stage 记录"]
    manifest["manifest artifact 与状态"]
    gate{"零失败、节点非空、无断链/孤立"}
    next["07 LCIA 计算"]
    stop["failed"]

    preflight --> request --> executor --> import --> report --> graphTool --> graph --> returned --> stage --> manifest --> gate
    import -. 超时 .-> operation
    gate -->|是| next
    gate -->|否| stop
```

## 契约与调用表

| 类型 | 契约、规则或接口 | 触发时机 | 生产者 → 消费者 | 校验与握手内容 | 失败处理 |
| --- | --- | --- | --- | --- | --- |
| 输入交接 | `harness/specs/public/references/schemas/handoff.schema.json` | 进入阶段前 | 05 → 06 | 当前 LCI 范围、数据库、分类和 `preflight_hash` 完整一致 | 不一致禁止写入 |
| 操作规则 | `harness/rules/openlca-operation/README.md` | 调用导入/读回前 | Agent → MCP 调用 | 唯一写工具、重新预检、固定 LCI 目录、保留原始返回 | hash 变化时拒绝写入 |
| MCP schema | `import_lci(preflight_hash, lci_dir, target_category, database_name)` | 预检交接后 | `sub-executor` ↔ `control_openlca` MCP | 重算范围/hash 后导入，持续写 operation journal 并返回逐项状态 | 部分成功也置 `failed` |
| 超时状态 | `get_import_operation(preflight_hash)`、`references/schemas/import-operation-status.schema.json` | 导入调用超时后 | `sub-executor` ↔ operation journal | 只读返回 running/success/partial/failed/rejected/indeterminate | running/indeterminate 禁止重试或 CLI 回退 |
| 确定性验收 | `references/scripts/validation.py` | 保存导入报告和模型图后 | Stage 06 证据 → 主编排 Agent | 核对 05/manifest/report hash、时间线、图状态、预期节点和情景图指纹 | `ok!=true` 不得标记 passed |
| 产物 schema | `harness/specs/06-openlca-import-readback/references/schemas/import-report.schema.json` | 保存导入报告前 | MCP 原始返回 → `import_report.json` | operation、数据库、分类、hash、计数、实体 UUID、错误和耗时 | schema 非法或 `failed_count>0` 停止 |
| MCP schema | `get_model_graph(product_system, expected_process_ids)` | 导入零失败后 | `sub-executor` ↔ `control_openlca` MCP | 从活动数据库读回节点、边、图指纹及预期节点 | Product System 不明或读回失败停止 |
| 产物 schema | `harness/specs/06-openlca-import-readback/references/schemas/model-graph.schema.json` | 保存模型图前 | MCP 原始返回 → model graph JSON | Product System ref、nodes、edges、graph fingerprint、broken/disconnected/missing expected | 空节点、断链、孤立或缺少预期节点置 `failed` |
| 返回交接 | `harness/specs/public/references/schemas/handoff.schema.json` | 导入和读回完成后 | `sub-executor` → 主编排 Agent | 两个产物的 artifact/hash、原始 evidence、错误和下一动作 | 不完整证据不得通过 |
| 阶段/清单 | `stage.schema.json`、`workflow-manifest.schema.json`（均位于 `harness/specs/public/references/schemas/`） | 阶段终止时 | 主编排 Agent → memory | 登记报告、模型图、状态和 issue IDs | 任一门禁失败置 `failed` |

## 维护联动

- 三个产物 schema 只属于 06；字段、版本或路径变化时同步 MCP 转换逻辑、阶段 spec、workflow adapter、质量 rubric 和契约测试。
- `preflight_hash` 不得在导入时被历史值或变化后的范围复用。
- 只有 import report 零失败且模型图满足连接性门禁，才向 07 交付。
