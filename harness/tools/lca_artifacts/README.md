# lca_artifacts

离线 MCP 入口：`uv run python harness/tools/lca_artifacts/main.py`。

工具由工作流 YAML 绑定到 02–04，运行上下文通过 LCA_RUN_ID、LCA_STAGE、LCA_ATTEMPT、LCA_ROLE、LCA_WORKSPACE 注入。01 仅接收编排器提供的文件清单，不绑定本工具。

| 工具 | 行为 |
| --- | --- |
| validate_artifacts(profile) | inventory/mapping/report 确定性校验，独立审计落盘 |
| get_validation_state(profile) | 检测输入变更，返回 not_run/passed/failed/stale |
| get_rework_status() | 同 run 04 返工复用资格与缺口 |
| render_report_tables() | 写者生成三个标记区；保留叙述 |
| read_artifact(path, sha256, offset=0, limit=2000, json_pointer=None) | 校验和验证后选取 JSON Pointer（如 /queries/0/items），再按字符切片；limit 最大 4000 |

公开响应 v2 统一为摘要加 artifact。可用 status 判断工具是否执行成功，检查本身的结论见 checks；stage 是否通过由 reviewer 决定。具体契约见 `harness/specs/public/references/evidence-contract.md`。

计算计划为 `workspace/outputs/reports/calculation-plan.json`：

```json
{"calculations":[{"product_system":"queried-system-uuid","impact_method":"queried-method-uuid","amount":1.0}]}
```

正式调用中必须使用查询得到的 UUID，以上仅为结构示意。同一系统和方法只配置一次，不同模型情景分别建 Product System。

报告浮点数统一显示 12 位有效数字，raw 保留完整精度；审查工具使用相同格式生成预期表格。get_rework_status 返回 scope=none 且 eligible=false 时，根据 changes 修复具体证据缺口，不能当作 calculation_changed 或 report_only。
