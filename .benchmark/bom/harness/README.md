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
| `bom-extract-01` | 无 | **无** | 产品 `executor`；无 skills | 共用 `bom-claims.yaml`（unit=原文短语） |
| `bom-extract-02` | 无 | **无**（技能到达用 **agent.rules**） | 产品 `executor` + **`bom-claims-flow`** + `rules/delivery/read-skills-first.yaml` + 薄 MCP `bom_claims_check`（只告警） | 同 01 共用 `bom-claims.yaml` |
| `bom-extract-03` | **有** | **无** | **三件套** orch+executor(助手)+reviewer（专用 agent）；**不挂技能** | 同 01 |
| `bom-extract-04` | **有** | status + provenance + knowledge-files | 产品 agent；executor=`bom-claims-read`+`ops`；reviewer=`bom-claims-review` | 短指针 `bom-claims-best.yaml` |

- **01 真薄**：题面 ≈ 短指令 + 案题 query；交付 claims submit。
- **02**：同 01 拓扑；挂 `bom-claims-flow` + executor `agent.rules: read-skills-first`（**node.inject 仍空**）+ 薄 MCP `bom_claims_check`。技能为重构版单文件 SKILL：读技能→grep 定位小窗读（不足可扩窗）→题意/图例锚定、只交所问→claims（`claim_id`、`value`+`unit` 成对；**unit 照抄原文单位短语**含限定语；SKILL 附评分器 `UNIT_NORMALIZATION` 同义表作规则词汇、非金标；evidence 可回源：文件/位置/逐字引文；原文不足时 evidence 以 `[推断]` 开头写依据）→`check_claims`（对照 evidence 整词匹配 unit 短语，只提醒、不删、不拦交卷）→submit；有数字就交、全无才弃权。无黑名单、无反例、不引用金标答案。**01/02/03 共用** `bom-claims.yaml`（unit=原文短语；`checks: []`；同义表只在 02 技能，不进 spec）。给法仍官方 query + `reference.md`。
- **03**：三件套（orchestrator 主交卷 / executor 写作者助手 / reviewer）；LangGraph 强制审核环；**不靠技能抬分**（04 再挂）。tip 不开批。
- **04 厚注入+reviewer**：技能拆自原 `bom-claims-best`；`bom-claims-best/` 仅兼容别名。

abstention 复用任一 extract stem（`--cases-root .benchmark/bom/abstention`），无单独 abstention orch。
