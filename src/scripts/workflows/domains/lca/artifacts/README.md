# LCA 产物工作流适配层

离线 MCP 入口：`uv run python src/scripts/workflows/domains/lca/artifacts/main.py`。

工具由工作流 YAML 绑定到 02–04。主编排每轮写入 `workspace/tmp/mcp-context/<run_id>/<stage>/<role>.json`，并以 `--context-file` 传给 MCP；进程每次调用重读该文件。`LCA_*` 环境变量仅为冗余。无 `--context-file` 时（GUI/探测）才回退环境变量或 standalone。01 仅接收编排器提供的文件清单，不绑定本工具。主编排在写者合法提交后运行确定性检查。

| 工具 | 行为 |
| --- | --- |
| submit_handoff(status, status_reason, …) | 由主机写入当前 assignment 的 handoff 路径并校验 schema（含 rework_scope） |
| validate_artifacts(profile) | inventory/mapping/report 确定性校验，独立审计落盘 |
| get_validation_state(profile) | 检测输入变更，返回 not_run/passed/failed/stale |
| get_rework_status() | 同 run 04 返工复用资格与缺口 |
| render_report_tables() | 写者生成三个标记区；保留叙述 |
| read_artifact(path, sha256, offset=0, limit=2000, json_pointer=None) | 校验和验证后选取 JSON Pointer（如 /queries/0/items），再按字符切片；limit 最大 4000 |

公开响应 v2 统一为摘要加 artifact。可用 status 判断工具是否执行成功，检查本身的结论见 checks；stage 是否通过由 reviewer 决定。具体契约见 `harness/specs/public/references/evidence-contract.md`。

计算计划为 `workspace/outputs/reports/calculation-plan.json`，保持 `calculations` 数组，每项包含 product_system、impact_method、amount。正式调用的系统与方法 UUID 必须经查询确认；新建前景系统在导入后确认。同一系统和方法只配置一次，不同模型情景分别建 Product System。

amount 为功能单位对应的目标参考流数量，以核实的默认参考单位表达；不能机械填写 1.0，也不因 Product System 设置 targetAmount 就自动采用其数值。检查器核对计划与调用一致性，功能单位换算仍由 reviewer 审查。归档、上下文和权威检查记录由工具维护，运行 Agent 只引用正式证据。

报告浮点数统一显示 12 位有效数字，raw 保留完整精度；审查工具使用相同格式生成预期表格。get_rework_status 返回 scope=none 且 eligible=false 时，根据 changes 修复具体证据缺口，不能当作 calculation_changed 或 report_only。

底层独立处理函数在 `harness/tools/lca_artifacts/`，不读取工作流上下文。
