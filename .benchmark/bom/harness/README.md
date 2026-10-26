# `.benchmark/bom/harness`

BOM 测评用的工作流 / 节点 / spec，与产品侧 `harness/` **同构**（`workflows/orchestrations|nodes`、`specs`）。

YAML 里的 `nodes:` / `produces.spec` 一律写**相对仓库根**的路径（禁止短名、禁止 `..`、禁止绝对路径），例如：

```yaml
nodes: [.benchmark/bom/harness/workflows/nodes/bom-extract-03.yaml]
produces:
  - {spec: .benchmark/bom/harness/specs/bom-claims.yaml, path: bom/claims.json}
```

API 开跑仍可用 orch 文件 stem（`workflow: bom-extract-03`）；`list_workflows` 会扫描
`harness/workflows/orchestrations/` 与本目录及 `.benchmark/lci/harness/` 的 `workflows/orchestrations/`。

agent 模板与规则正文继续共用 `harness/workflows/agents/`、`harness/rules/`（节点 `inject:` 照常引用）。

## 档位（工作流名后加 01–04）

| stem | 含义 | 本仓状态 |
| --- | --- | --- |
| `bom-extract-01` | **真·薄** | 预留，尚未建 orch |
| `bom-extract-02` | **薄编排（无 reviewer）**；提示词注入同 best | 预留，尚未建 orch |
| `bom-extract-03` | **薄注入，但有 reviewer 编排**（现网在跑的「薄注入+双角色」树） | 已有（原 `bom-extract`） |
| `bom-extract-04` | **最好**（短指针 spec + `bom-claims-best`） | 已有（原 `bom-extract-best`） |

本轮图1仍只对比 **03 → 04**（extract36）；01/02 未实现，勿 invent。

- 03 spec：`.benchmark/bom/harness/specs/bom-claims.yaml`（薄注入长散文）
- 04 spec：`.benchmark/bom/harness/specs/bom-claims-best.yaml`（短指针）
- 04 技能：`harness/tools/skills/bom-claims-best/SKILL.md`

abstention 复用 `bom-extract-03` / `bom-extract-04`（`--cases-root .benchmark/bom/abstention`），无单独 abstention orch。
