# 工作流 YAML（v5）

装配在 `harness/workflows/`：`orchestrations/` → `nodes/` → `agents/`。评测档可在 `.benchmark/*/harness/workflows/` 用**仓库根相对路径**引用。

## 角色与默认最佳实践

- **可自由编排** agents + `flow.edges`；不要额外「更死骨架开关」。
- **有编排节点默认最佳实践（三件套）**：
  1. `orchestrator`：主 agent（`deliver.submit: artifact`），**不改文件**，只调度/汇总交卷
  2. `executor`：写产物；三件套里可省略 `deliver`（无交卷助手），回合结束走无条件边
  3. `reviewer`：`deliver.submit: verdict`
- **薄档**（如 extract 01/02）：可只有单个 `executor`（兼写兼交卷）。
- 每个节点**恰好一个** `deliver.submit: artifact`；`flow.start` 可不等于该主 agent，但主 agent 必须从 start 可达。

## flow 预算（无节点共用 max_steps）

- 每 agent：`deliver.max_turns` 或节点覆盖 `max_turns`（默认 **30**）
- `flow.recursion_limit`：可选 LangGraph 保险丝；省略则按各 agent 回合预算推导
- `flow.same_tool_limit`：默认 **3**（连续相同工具+参数熔断）；`0` 关闭
- 节点间 `max_redos`、断线 Retry 与回合预算分开

## LangGraph 强制（三件套 default_flow）

executor → reviewer；`reject` → executor（`max`）→ reviewer；`approve` → orchestrator → `done`。
不要靠提示词模拟这条边。

## 改完

跑 `uv run pytest src/tests/t_workflow -q`。长文底本：`docs/architecture/WORKFLOW_DESIGN.md`、`DELIVERY_PRIMARY_AGENT.md`。
