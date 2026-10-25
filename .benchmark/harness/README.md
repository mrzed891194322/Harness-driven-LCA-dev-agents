# `.benchmark/harness`

测评用的工作流 / 节点 / spec，与产品侧 `harness/` **同构**（`workflows/orchestrations|nodes`、`specs`）。

YAML 里的 `nodes:` / `produces.spec` 一律写**相对仓库根**的路径（禁止短名、禁止 `..`、禁止绝对路径），例如：

```yaml
nodes: [.benchmark/harness/workflows/nodes/bom-extract.yaml]
# 或产品树：
# nodes: [harness/workflows/nodes/lca-bom.yaml]
produces:
  - {spec: .benchmark/harness/specs/bom-claims.yaml, path: bom/claims.json}
```

API 开跑仍可用 orch 文件 stem（`workflow: bom-extract`）；`list_workflows` 会扫描
`harness/workflows/orchestrations/` 与本目录的 `workflows/orchestrations/`。

agent 模板与规则正文继续共用 `harness/workflows/agents/`、`harness/rules/`（节点 `inject:` 照常引用）。

不同 harness 条件应对应不同工作流文件，放在本目录；最完整条件的专用技能/提示词可另补，本树只保证「测评变体不进产品 harness」。
