# `.benchmark/bom/harness`

BOM 测评用的工作流 / 节点 / spec，与产品侧 `harness/` **同构**（`workflows/orchestrations|nodes`、`specs`）。

YAML 里的 `nodes:` / `produces.spec` 一律写**相对仓库根**的路径（禁止短名、禁止 `..`、禁止绝对路径），例如：

```yaml
nodes: [.benchmark/bom/harness/workflows/nodes/bom-extract.yaml]
produces:
  - {spec: .benchmark/bom/harness/specs/bom-claims.yaml, path: bom/claims.json}
```

API 开跑仍可用 orch 文件 stem（`workflow: bom-extract`）；`list_workflows` 会扫描
`harness/workflows/orchestrations/` 与本目录及 `.benchmark/lci/harness/` 的 `workflows/orchestrations/`。

agent 模板与规则正文继续共用 `harness/workflows/agents/`、`harness/rules/`（节点 `inject:` 照常引用）。

## 最好条件

- orch / 节点：`bom-extract-best`（薄档 `bom-extract` 不动）
- spec：`.benchmark/bom/harness/specs/bom-claims-best.yaml`（短指针）
- 技能：`harness/tools/skills/bom-claims-best/SKILL.md`（节点 `tools.skills` 挂接）

