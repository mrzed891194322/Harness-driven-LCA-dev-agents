# `.benchmark/bom/harness`

BOM 测评用的工作流 / 节点 / spec，与产品侧 `harness/` **同构**（`workflows/orchestrations|nodes`、`specs`）。
专用 agent 可放本树 `workflows/agents/`，节点里用**仓根相对路径**引用（02–04 均用专用三角色 agent）。

YAML 里的 `nodes:` / `produces.spec` 一律写**相对仓库根**的路径（禁止短名、禁止 `..`、禁止绝对路径），例如：

```yaml
nodes: [.benchmark/bom/harness/workflows/nodes/bom-extract-01.yaml]
produces:
  - {spec: .benchmark/bom/harness/specs/bom-claims.yaml, path: bom/claims.json}
```

API 开跑仍可用 orch 文件 stem（`workflow: bom-extract-01`）；`list_workflows` 会扫描
`harness/workflows/orchestrations/` 与本目录及 `.benchmark/lci/harness/` 的 `workflows/orchestrations/`。

规则正文继续共用 `harness/rules/`（通过节点角色的 `rules:` 绑定）。
全局三条（`rules/global/00-redlines` / `10-language` / `20-knowledge`）由宿主对所有档注入，不写在节点 YAML。

## 档位

02/03 基于 04 拆分，均为单节点 Orchestrator + Executor + Reviewer，沿用现有 LangGraph 三角色图；不是逐档叠加。01 与 04 保留作对照。

| stem | 角色与侧重 | 技能 / MCP / 内容规则 | produce spec |
| --- | --- | --- | --- |
| `bom-decomposition-01` | 产品组成（PCFBench task1） | 原装配 | `bom-decomposition.yaml` |
| `bom-extract-01` | 单 executor，官方口径 | 无技能、无 MCP；官方英文 rule | `bom-claims-01.yaml` |
| `bom-extract-02` | 三角色，技能与工具工作流 | executor `bom-claims-flow-02`；reviewer `bom-claims-review-02` + `bom_claims_check`；共用短 rule `bom-extraction-02-03` | `bom-claims-02.yaml`，沿用 04 schema 形状，`checks: []` |
| `bom-extract-03` | 三角色，最小硬编排 | 无技能；reviewer `bom_claims_check`；同一短 rule `bom-extraction-02-03` | `bom-claims-03.yaml`，必填数值 `value` 与非空 `unit`，`checks: []` |
| `bom-extract-04` | 三角色，原完整基线 | executor `bom-claims-flow-04`；reviewer `bom-claims-review` + MCP；共用 `bom-extraction-04` | `bom-claims-04.yaml` |

- **02 技能与工具工作流**：executor 先按题面写 checklist，再取证、抽取、自查；reviewer 核实清单，调用 MCP（含 `numeric_duplicates=true`），独立回原文后交 verdict。checklist 是笔记，不是宿主验收协议；语义约束由技能与审核落实，不新增 checklist、条数、覆盖或数值去重硬闸。
- **03 最小硬编排**：agent 只承载职责、派工与 verdict 契约，不挂长技能、不要求 executor checklist 文件。reviewer 直接按题面组织 MCP 清单并核对原文；schema 拒收缺失/空值/非数值 value 和空白 unit。空 claims 仍合法，是否确无答案由 reviewer 审核，不用启发式告警强行拦截。
- **共同机制**：orchestrator 唯一交 artifact，executor 只写产物，reviewer 只读产物并交 verdict。两档均走默认 LangGraph 三角色图和原有预算；宿主 schema、权限、最新 approve 才能 done 的门禁不移除。编排者读取本档 `runs/bom-extract-0N/reviewer/attempt_<N>/submit.json` 中最大 N 的已提交 verdict；reject 后派返工再复审，旧 feedback 不覆盖新 approve，审后修改须复审。各角色会话按现有运行机制连续。
- **内容口径**：02/03 共用从 04 提炼的短规则，覆盖题面对象与统计粒度、过报邻档、单位符号照抄、范围端点、总量与独立分项、同对象同指标同值合并及连续证据。避免同时挂载官方中点规则造成冲突。MCP 告警仅作回原文核查线索，不决定语义裁决。
- **路径**：产物仍为 `workspace/runs/_run/artifacts/bom/claims.json`；中间笔记放 `workspace/runs/_run/notes/bom-extract-02/<role>/` 或 `bom-extract-03/<role>/`。02 checklist 为其 `executor/checklist.json`；03 无强制清单文件；04 路径不变。

旧 02 的单 executor 与旧 03 的通用角色绑定由新档就地替换；旧 `bom-claims-flow` 和通用 agent 文件不再由这两档引用，保留以免影响其他调用。04 的 rule、技能、agent、spec 均不修改。

abstention 复用任一 extract stem（`--cases-root .benchmark/bom/abstention`），无单独 abstention orch。
