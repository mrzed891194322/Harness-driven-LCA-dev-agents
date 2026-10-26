# `.benchmark/lci/harness`

LCI / mapping 测评用的 orch / node / spec（与产品 `harness/` 同构）。

## 冒烟工作流

| API stem | 说明 |
| --- | --- |
| `lci-mapping` | 封闭候选集映射；不查 openLCA、不依赖 `bom/bom.json`。产物 `artifacts/mapping/mapping.json`。 |

YAML 里的 `nodes:` / `produces.spec` 一律写**相对仓库根**的路径。API 开跑用 orch stem（`workflow: lci-mapping`）；`list_workflows` 会扫描本目录的 `workflows/orchestrations/`。

产品侧全量映射节点仍是 `harness/workflows/nodes/lca-mapping.yaml`（要 BOM + openLCA），**不要**拿来跑 PCFBench task3 封闭集冒烟。

agent 模板与规则正文继续共用 `harness/workflows/agents/`、`harness/rules/`。

## 最好条件

- orch / 节点：`lci-mapping-best`（薄档 `lci-mapping` 不动）
- spec：`.benchmark/lci/harness/specs/lci-mapping-closed-best.yaml`（短指针）
- 技能：`harness/tools/skills/lci-mapping-best/SKILL.md`（节点 `tools.skills` 挂接）

