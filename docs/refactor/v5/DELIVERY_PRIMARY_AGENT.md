# 交卷主 agent、依据规则、去掉计划核对

状态：已实现 §8.1–8.3（2026-10-23）；§8.4 产物依据字段可选、未做。破坏式：改编排与校验，不保留 intake 门禁兼容。

相关：`docs/refactor/WORKFLOW_DESIGN.md` §2–3；`src/backend/workflow/config.py`（`SUBMIT_VALUES` / `deliver.submit`）；现有 `harness/workflows/agents/{executor,reviewer}.yaml`。

## 1. 目标

1. 宿主只做文件级门禁（`requires`）；内容够不够由主 agent 判断。
2. 每个节点有且仅有一个**主 agent**（`deliver.submit: artifact`），唯一能交节点产物。
3. Reviewer / 子 agent 不交节点结果；工具型 agent 不挂交卷规则。
4. 去掉 `lca-intake`（计划核对）；BOM 起直接读 plan/资料。
5. 「可凭知识补」vs「必须报不足」的**判断原则**写在 rules；**可选状态列表**写在 spec（或节点/交卷工作流配置），不写成长段提示词。

## 2. 角色与交卷

| 角色 | `deliver.submit` | 职责 |
|------|------------------|------|
| 主 agent | `artifact` | 写产物并 `submit`：`status ∈ {done, blocked, redo_upstream}`（以 `SUBMIT_VALUES["artifact"]` 为准） |
| Reviewer | `verdict` | 只评主 agent 产物：`verdict ∈ {approve, reject, approve_redo_upstream, terminate}`；不改产物 |
| 子 agent / 工具角色 | 无 / 不挂交卷包 | 查资料、写脚本等，结果回给主 agent |

节点内 flow（与现默认一致）：主 agent `done` → reviewer；`blocked` → 节点 blocked；`redo_upstream` → reviewer 审批；reviewer `approve` → 节点 done；`reject` → 回主 agent；`approve_redo_upstream` → 外层 redo；`terminate` → 停止。

## 3. 配置与校验

- **主 agent 判定**：节点 `agents` 里 `deliver.submit == artifact` 的那个（模板解析后）。不另加 `primary:` 字段。
- **硬校验**（`load_node` / 编排加载，`ConfigError`）：
  - 每个节点 **恰好一个** `deliver.submit: artifact`（0 或多个都失败）。
  - 已有：`flow.start` 必须是 artifact agent；flow 边的 `when` 必须属于该 agent 的 submit 枚举；`redo_upstream` 须经 verdict 审批。
- Reviewer 可有 0 或 1 个（现 LCA 节点为 1）；无 reviewer 时沿用现「仅 artifact 终态」默认 flow。
- 子 agent：可出现在 `agents` 但不进入交卷边，或仅由主 agent 通过工具/会话调用（实现阶段二选一，默认先不进 flow）。

## 4. Rules vs Spec

**Rules（提示词，可选注入）**

- `harness/rules/delivery/status.yaml`：主 agent 何时选 done / blocked / redo_upstream（语义，不列死枚举表之外的值）。
- `harness/rules/delivery/provenance.yaml`：依据标注；何时可凭模型知识补全并**必须标明**；何时必须 `blocked`/`stop` 报不足。
- 只挂到主 agent（及需要审依据的 reviewer）；工具型 agent 不挂。

**Spec / 交卷配置（机器可读）**

- 状态枚举列表与 schema 校验（已有 submit MCP schema + `SUBMIT_VALUES`）；节点 `produces[].spec` 约束产物字段（含依据列/字段，若该阶段需要）。
- Spec **不写**分界判断长文；只规定「允许出现哪些状态/字段」。

## 5. 编排改动（full-lca）

- `harness/workflows/orchestrations/full-lca.yaml`：`nodes: [lca-bom, lca-mapping, lca-report]`（去掉 `lca-intake`）。
- `lca-bom`：删除 `requires: [intake/intake.md]`；改为依赖 plan（及声明资料路径，按现 plan 注入方式）；缺关键输入由主 agent `blocked` + 依据规则，或宿主对 plan 文件本身做 `requires`。
- 删除或停用 `harness/workflows/nodes/lca-intake.yaml`、`harness/specs/lca-intake.yaml`（优先删净，避免 GUI 再出现「计划核对」）。
- 更新 `rules/lca/knowledge-files.yaml` 等对 intake 的点名；`docs/ARTIFACTS.md` / `WORKFLOW_DESIGN` 示例节点列表同步。
- `revise-lca` / demo：若引用 intake，一并去掉。

## 6. 宿主行为（不变的边界）

- 节点开始：解析 `requires` → 缺文件则节点 failed/blocked，**不启** agent。
- 不解析产物「内容是否够」；那是主 agent + reviewer + rules/spec。

## 7. 与技能 / 共享文档

- 实现后：`docs/PROJECT_LAYOUT.md`、`docs/refactor/WORKFLOW_DESIGN.md`（或本文链过去）作为 `harness-edit` / `code-dev` 共享底本；改 YAML 契约时同步改文档。
- `harness-edit` 生成节点时必须能通过「恰好一个 artifact submit」校验。

## 8. 建议实现顺序

1. 配置校验：每节点恰好一个 `artifact` submit。
2. 规则包 `delivery/status` + `delivery/provenance`；挂到 LCA 主 agent / reviewer。
3. 编排去掉 intake；改 bom requires；删 intake 节点/spec；文档与 ARTIFACTS 对齐。
4. （可选）产物 schema 增加依据字段；GUI 展示另议。

## 9. 非目标（本页不做）

- 运行时拓扑叠状态（UI 另做）。
- LCA 跨库。
- 细粒度按 Codex/Claude 分权限。
