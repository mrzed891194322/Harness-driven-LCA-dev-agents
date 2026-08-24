# 07 LCIA 计算与报告 Schema 握手映射

本文是维护索引，不替代本阶段 spec、本阶段 schema/template、openLCA 操作规则或 MCP 运行时 schema。公共 handoff / stage / manifest 握手机制见 [`../public/references/handshake-common.md`](../public/references/handshake-common.md)。

## 握手流程

```mermaid
flowchart TD
    graph["06 import report + model graph"]
    request["计算请求 handoff"]
    executor["sub-executor"]
    calc["calculate_product_system"]
    raw["raw/slug.json"]
    manifestOut["calculation_manifest.json"]
    report["lca_report.md"]
    returned["计算返回 handoff"]
    gate{"结果非空、资源释放、全部契约通过"}
    done["completed"]
    stop["failed / needs_review"]

    graph --> request --> executor --> calc --> raw --> manifestOut --> report --> returned --> gate
    gate -->|是| done
    gate -->|否| stop
```

## 契约与调用表（阶段特有）

| 类型 | 契约、模板或接口 | 触发时机 | 生产者 → 消费者 | 校验与握手内容 | 失败处理 |
| --- | --- | --- | --- | --- | --- |
| 输入 schema | `06/.../import-report.schema.json`、`model-graph.schema.json` | 进入阶段前 | 06 → 07 | 导入零失败、图状态成功、节点非空且无断链/孤立节点 | 不满足禁止计算 |
| 操作规则 | `harness/rules/openlca-operation/README.md` | 调用计算前 | Agent → MCP 调用 | 活动 endpoint、正式 UUID、只读计算和资源释放 | 工具错误保存原始证据 |
| MCP schema | `calculate_product_system(product_system, impact_method, amount, allocation, regionalized, costs, parameters)` | 06 门禁通过后 | `sub-executor` ↔ `control_openlca` MCP | 类别名称/UUID、数值、单位、设置、时间和 `resource_released` | 空类别或未释放资源置 `failed` |
| 产物 schema | `references/schemas/raw-lcia-results.schema.json` | 保存原始结果前 | MCP 原始返回 → raw JSON | Product System、方法、计算设置、影响类别和资源释放状态 | schema 非法不得生成完成结论 |
| 产物 schema | `references/schemas/calculation-manifest.schema.json` v3 | 保存计算清单前 | 计算证据 → calculation manifest | 共享 database/method/tool、每个情景 calculation 及每对情景 comparison check | 数组为空、任一 calculation 失败、比较对缺失或 v2 workaround 均停止 |
| 确定性验收 | `references/scripts/validation.py` | raw、图和清单齐全后 | Stage 07 证据 → 主编排 Agent | 核对 raw 存在与非空结果、全部情景对；相同 LCIA 而预期过程不同时需解释 | failed 停止，needs_review 不得 completed |
| 报告模板 | `references/templates/lca_report.md` | raw 与清单通过后 | 结构化结果 → `lca_report.md` | 核心数值回链类别 UUID 和 raw 路径，并保留声明边界 | 不支持 ISO 认证或比较优势声明 |

## 维护联动

- 07 的 schema、模板、必需文件或语义变化时，必须同步计算转换逻辑、workflow、质量评价 artifact coverage/rubric 和契约测试。
- 报告模板不能成为新的数据源；所有核心数值必须来自通过 schema 的 raw 结果。
- `completed` 不是工具成功的别名，而是 06/07 全部结构化门禁的联合结论。
