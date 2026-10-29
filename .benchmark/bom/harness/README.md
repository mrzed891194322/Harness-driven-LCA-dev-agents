# `.benchmark/bom/harness`

BOM 测评用的工作流 / 节点 / spec，与产品侧 `harness/` **同构**（`workflows/orchestrations|nodes`、`specs`）。
专用 agent 可放本树 `workflows/agents/`，节点里用**仓根相对路径**引用（勿复用产品 `executor`/`reviewer` 短名——03 起）。

YAML 里的 `nodes:` / `produces.spec` 一律写**相对仓库根**的路径（禁止短名、禁止 `..`、禁止绝对路径），例如：

```yaml
nodes: [.benchmark/bom/harness/workflows/nodes/bom-extract-01.yaml]
produces:
  - {spec: .benchmark/bom/harness/specs/bom-claims.yaml, path: bom/claims.json}
```

API 开跑仍可用 orch 文件 stem（`workflow: bom-extract-01`）；`list_workflows` 会扫描
`harness/workflows/orchestrations/` 与本目录及 `.benchmark/lci/harness/` 的 `workflows/orchestrations/`。

规则正文继续共用 `harness/rules/`（节点 `inject:` 照常引用）。
全局三条（`rules/global/00-redlines` / `10-language` / `20-knowledge`）由宿主对所有档注入，不写在节点 YAML。

## 档位（工作流名后加 01–04 · 同一骨架只拨开关）

| stem | reviewer | node.inject | skills / agents | produce spec |
| --- | --- | --- | --- | --- |
| `bom-decomposition-01` | 产品组成（PCFBench task1）真薄 | 已有 |
| `bom-extract-01` | 无 | **无** | 产品 `executor`；无 skills | 薄短 `bom-claims.yaml` |
| `bom-extract-02` | 无 | **无** | 产品 `executor` + **`bom-claims-flow`**（轻自检+短防多报） | 同 01：`bom-claims.yaml`（短符号） |
| `bom-extract-03` | **有** | **无** | **专用** `.benchmark/.../agents/bom-extract-{executor,reviewer}.yaml`；**不挂技能** | 同 01 |
| `bom-extract-04` | **有** | status + provenance + knowledge-files | 产品 agent；executor=`bom-claims-read`+`ops`；reviewer=`bom-claims-review` | 短指针 `bom-claims-best.yaml` |

- **01 真薄**：题面 ≈ 短指令 + 案题 query；交付 claims submit。
- **02**：同 01 拓扑；只多挂 `bom-claims-flow`（轻自检、禁弃权；黑名单仅 h/°C；单位短符号+硬反例；短防多报；`refs/`）。**produce 同 01** 共享 `bom-claims.yaml`。`bom-claims-unit-phrase.yaml` 废弃（`f4ff815`：Nemotron `…163522`≈0.503 vs `…144453` −0.026；原文短语 vs 规范化金标）。给法仍官方 query + `reference.md`。旧名 `bom-claims-slim` 已弃用占位。
- **03**：专用薄 agent 编排（职责写在 agent 提示词）；**本档不靠技能抬分**（04 再挂）。对照基线 TAG 记 HOWTO；tip 不开批。
- **04 厚注入+reviewer**：技能拆自原 `bom-claims-best`；`bom-claims-best/` 仅兼容别名。

abstention 复用任一 extract stem（`--cases-root .benchmark/bom/abstention`），无单独 abstention orch。
