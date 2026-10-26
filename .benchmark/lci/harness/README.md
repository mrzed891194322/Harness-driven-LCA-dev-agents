# `.benchmark/lci/harness`

LCI / mapping / triage 测评用的 orch / node / spec（与产品 `harness/` 同构）。

## 档位（工作流名后加 01–04）

| 档 | 含义 |
| --- | --- |
| **01** | 真·薄 |
| **02** | 薄编排（无 reviewer）；提示词注入同 best |
| **03** | 薄注入，但有 reviewer 编排 |
| **04** | 最好 |

| API stem | 说明 | 状态 |
| --- | --- | --- |
| `lci-mapping-01` / `lci-triage-01` | 真·薄 | 预留未建 |
| `lci-mapping-02` / `lci-triage-02` | 薄编排无 reviewer；注入同 best | 预留未建 |
| `lci-mapping-03` | 封闭候选集映射（薄注入 + reviewer）；产物 `artifacts/mapping/mapping.json` | 已有 |
| `lci-mapping-04` | 最好：短指针 spec + `lci-mapping-best` | 已有 |
| `lci-triage-03` | PCFBench task2 映射分流（薄注入 + reviewer）；产物 `artifacts/triage/triage.json` | 已有 |
| `lci-triage-04` | 最好：短指针 spec + `lci-triage-best` | 已有 |

本轮仍以已有 **03 / 04** 为主；01/02 勿 invent。

YAML 里的 `nodes:` / `produces.spec` 一律写**相对仓库根**的路径。API 开跑用 orch stem；`list_workflows` 会扫描本目录的 `workflows/orchestrations/`。

产品侧全量映射节点仍是 `harness/workflows/nodes/lca-mapping.yaml`（要 BOM + openLCA），**不要**拿来跑 PCFBench task3 封闭集冒烟。

agent 模板与规则正文继续共用 `harness/workflows/agents/`、`harness/rules/`。
