# 07 LCIA 计算与报告 Schema 握手映射

本文是维护索引，不替代本阶段 spec、本阶段 schema/template、openLCA 操作规则或 MCP 运行时 schema。

## 握手流程

```mermaid
flowchart TD
    graph["06 import report + model graph"]
    request["计算请求 handoff"]
    executor["sub-executor"]
    calc["calculate_product_system"]
    raw["raw/slug.json<br/>raw-lcia-results.schema.json"]
    manifestOut["calculation_manifest.json<br/>calculation-manifest.schema.json"]
    report["lca_report.md<br/>lca_report template"]
    returned["计算返回 handoff"]
    stage["07 stage 记录"]
    workflow["workflow manifest"]
    gate{"结果非空、资源释放、全部契约通过"}
    done["completed"]
    stop["failed / needs_review"]

    graph --> request --> executor --> calc --> raw --> manifestOut --> report --> returned --> stage --> workflow --> gate
    gate -->|是| done
    gate -->|否| stop
```

## 契约与调用表

| 类型 | 契约、模板或接口 | 触发时机 | 生产者 → 消费者 | 校验与握手内容 | 失败处理 |
| --- | --- | --- | --- | --- | --- |
| 输入 schema | `harness/specs/06-openlca-import-readback/references/schemas/import-report.schema.json`、`model-graph.schema.json` | 进入阶段前 | 06 → 07 | 导入零失败、图状态成功、节点非空且无断链/孤立节点 | 不满足禁止计算 |
| 交接 schema | `harness/specs/public/references/schemas/handoff.schema.json` | 委派计算前后 | 主编排 Agent ↔ `sub-executor` | Product System、方法、功能单位、设置、输入 hashes、输出 artifacts、错误和下一动作 | 返回不完整不得完成 |
| 操作规则 | `harness/rules/openlca-operation/README.md` | 调用计算前 | Agent → MCP 调用 | 活动 endpoint、正式 UUID、只读计算和资源释放 | 工具错误保存原始证据 |
| MCP schema | `calculate_product_system(product_system, impact_method, amount, allocation, regionalized, costs, parameters)` | 06 门禁通过后 | `sub-executor` ↔ `control_openlca` MCP | 类别名称/UUID、数值、单位、设置、时间和 `resource_released` | 空类别或未释放资源置 `failed` |
| 产物 schema | `harness/specs/07-lcia-calculation-reporting/references/schemas/raw-lcia-results.schema.json` | 保存原始结果前 | MCP 原始返回 → raw JSON | Product System、方法、计算设置、影响类别和资源释放状态 | schema 非法不得生成完成结论 |
| 产物 schema | `harness/specs/07-lcia-calculation-reporting/references/schemas/calculation-manifest.schema.json` | 保存计算清单前 | 计算证据 → calculation manifest | 数据库、对象/method ref、FU、分配/参数、工具版本、raw 路径/hash | schema 非法停止 |
| 报告模板 | `harness/specs/07-lcia-calculation-reporting/references/templates/lca_report.md` | raw 与清单通过后 | 结构化结果 → `lca_report.md` | 核心数值回链类别 UUID 和 raw SHA-256，并保留声明边界 | 不支持 ISO 认证或比较优势声明 |
| 阶段/清单 | `stage.schema.json`、`workflow-manifest.schema.json`（均位于 `harness/specs/public/references/schemas/`） | 最终验收时 | 主编排 Agent → memory | 登记 06/07 全部 artifacts、状态、证据和 issues | 仅全部门禁有结构化证据时 `completed` |

## 维护联动

- 07 的 schema、模板、必需文件或语义变化时，必须同步计算转换逻辑、workflow adapter、质量评价 artifact coverage/rubric 和契约测试。
- 报告模板不能成为新的数据源；所有核心数值必须来自通过 schema 的 raw 结果。
- `completed` 不是工具成功的别名，而是 06/07 全部结构化门禁的联合结论。
