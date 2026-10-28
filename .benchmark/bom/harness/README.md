# `.benchmark/bom/harness`

BOM 测评用的工作流 / 节点 / spec，与产品侧 `harness/` **同构**（`workflows/orchestrations|nodes`、`specs`）。

YAML 里的 `nodes:` / `produces.spec` 一律写**相对仓库根**的路径（禁止短名、禁止 `..`、禁止绝对路径），例如：

```yaml
nodes: [.benchmark/bom/harness/workflows/nodes/bom-extract-01.yaml]
produces:
  - {spec: .benchmark/bom/harness/specs/bom-claims.yaml, path: bom/claims.json}
```

API 开跑仍可用 orch 文件 stem（`workflow: bom-extract-01`）；`list_workflows` 会扫描
`harness/workflows/orchestrations/` 与本目录及 `.benchmark/lci/harness/` 的 `workflows/orchestrations/`。

agent 模板与规则正文继续共用 `harness/workflows/agents/`、`harness/rules/`（节点 `inject:` 照常引用）。
全局三条（`rules/global/00-redlines` / `10-language` / `20-knowledge`）由宿主对所有档注入，不写在节点 YAML。

## 档位（工作流名后加 01–04 · 同一骨架只拨开关）

| stem | reviewer | node.inject | skills | produce spec |
| --- | --- | --- | --- | --- |
| `bom-decomposition-01` | 产品组成（PCFBench task1）真薄 | 已有 |
| `bom-extract-01` | 无 | **无** | 无 | 薄短 `bom-claims.yaml` |
| `bom-extract-02` | 无 | **无**（同 01） | **`bom-claims-slim`**（executor） | 同 01 |
| `bom-extract-03` | **有** | **无**（同 01/02） | executor=`bom-claims-slim`；reviewer=`bom-claims-review` | 同 01 |
| `bom-extract-04` | **有** | status + provenance + knowledge-files | executor=`bom-claims-read`+`bom-claims-ops`；reviewer=`bom-claims-review` | 短指针 `bom-claims-best.yaml` |

- **01 真薄**：题面 ≈ 短指令 + 案题 query；交付 claims submit；环境门留环境，长 schema 不灌进提示散文。
- **02**：与 01 **同拓扑**（单 executor、无 reviewer、无 node.inject）；仅挂薄技能 `bom-claims-slim`（压 B2 多报 / B3 单位硬伤）。给法仍官方 query + `reference.md`。
- **03**：在 02 之上 **加 reviewer**（挂 `bom-claims-review`：必须读长文；无支持→删压 B2；单位照抄禁换算压 B3；漏报高门槛才补）。executor 仍只挂 slim；**无**厚 inject / 无 read+ops。对照基线 TAG `opencode-deepseek-flash-extract02-20261029-003412`（兼看 vs `…extract01-…233421`）—本档 tip 只钉 workflow，**不开批**。
- **04 厚注入+reviewer**：executor 挂 read+ops（拆自原 `bom-claims-best`）；`bom-claims-best/` 目录仅留兼容别名。
- 双单位：厚技能 = 只留一档 `(value,unit)`；薄 spec = 不写「并列双单位各建一条」。

abstention 复用任一 extract stem（`--cases-root .benchmark/bom/abstention`），无单独 abstention orch。
