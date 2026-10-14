# 规格

`harness/specs/<stage-id>/` 是该阶段的机器契约，不放 Markdown。阶段目录里常见这几份：

| 文件 | 作用 |
| --- | --- |
| `spec.yaml` | `inputs`、`deliverables`（路径、格式、schema、example）、`acceptance`、`permissions`、`lifecycle`、`handoff` |
| `acceptance.yaml` | `host_checks`、按交付物的 submit 检查、`review_points` |
| `permissions.yaml` | 本阶段每个角色引用哪条权限规则 |
| `deliverables/*.schema.json` | 交付物 JSON Schema |
| `examples/` | 与 schema 对应的例子 |

权限规则本体在 `harness/specs/shared/permissions/`（如 `worker-default.yaml`、`reviewer.yaml`）。handoff schema 在 `harness/specs/shared/handoff.schema.json`。

`stages[].spec` 的值就是阶段目录名。改交付路径时同时改 schema、example 和验收；提示词里不要复制字段清单。`spec_mcp` 在会话开头注入 `get_spec()`，agent 用它 `submit` / `submit_handoff`。
