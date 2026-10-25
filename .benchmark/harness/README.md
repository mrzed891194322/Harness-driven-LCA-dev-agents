# `.benchmark/harness`

测评用的工作流 / 节点 / spec，与产品侧 `harness/` **同构**（`workflows/orchestrations|nodes`、`specs`）。

加载器会在短名查找时先搜这里，再回退 `harness/`。也可在 YAML 里写**相对仓库根**的路径（含 `/` 或以 `.` 开头），例如：

```yaml
produces:
  - {spec: .benchmark/harness/specs/bom-claims.yaml, path: bom/claims.json}
```

短名示例：`bom-extract` orch / node、`bom-claims` spec 都在本树。产品 `full-lca`、`lca-bom` 等仍只在 `harness/`。

agent 模板与规则正文继续共用 `harness/workflows/agents/`、`harness/rules/`（节点 `inject:` 照常引用）。

不同 harness 条件应对应不同工作流文件，放在本目录；最完整条件的专用技能/提示词可另补，本树只保证「测评变体不进产品 harness」。
