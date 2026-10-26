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

| stem | 含义 |
| --- | --- |
| `bom-extract-01` | 真·薄（预留，本轮未建） |
| `bom-extract-02` | 产品默认薄编排（预留） |
| `bom-extract-03` | 中间：有编排、无 best 技能（原 `bom-extract`） |
| `bom-extract-04` | 最好：短指针 spec + `bom-claims-best`（原 `bom-extract-best`） |

- 03 spec：`.benchmark/bom/harness/specs/bom-claims.yaml`
- 04 spec：`.benchmark/bom/harness/specs/bom-claims-best.yaml`
- 04 技能：`harness/tools/skills/bom-claims-best/SKILL.md`

abstention 复用 `bom-extract-03` / `bom-extract-04`（`--cases-root .benchmark/bom/abstention`），无单独 abstention orch。
