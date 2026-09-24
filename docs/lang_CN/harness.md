# Harness 契约目录

`harness/` 是工作流**装配图与注入内容**，不是 Python 编排实现。根目录只允许：

```text
LCA-main.yaml
LCA-revise.yaml
knowledge/
tools/
rules/
specs/
```

| 路径 | 作用 |
| --- | --- |
| `LCA-main.yaml` / `LCA-revise.yaml` | 完整独立装配图（无 reuse / stage_overrides） |
| `specs/` | 机器契约：`spec.yaml` + JSON Schema + examples（无 Markdown） |
| `rules/` | Agent 自然语言：project / lca / tools / stages / assignments |
| `tools/` | `mcp/`、`host_action/`、`shared/` 三层 |
| `knowledge/` | 用户参考资料落点 |

编排引擎在 [`src/core/`](../src/core/)。Agent 能力经 YAML 注册的 stdio MCP 进入会话；Core 验收经 Host Action。core 不 import `harness.tools`。

## 注入链

```text
Workflow YAML
  → 注册 rules / knowledge / mcp / host_action
  → stages[].spec → StageSpec（inputs/outputs/acceptance/lifecycle/handoff）
  → assignments[].rules.add → 角色与阶段自然语言
  → TaskBundle
  → core 执行循环
  → Core run_host_action 跑验收/lifecycle；worker 会话调业务 MCP
```

## 启动

```bash
uv run python src/scripts/workflow.py --workflow harness/LCA-main.yaml
uv run python src/scripts/workflow.py --workflow harness/LCA-revise.yaml
```

YAML 只引用 path / ID，不内嵌任务正文。自然语言只在 `rules/`。
