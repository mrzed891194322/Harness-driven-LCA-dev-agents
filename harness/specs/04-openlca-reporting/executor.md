# 04 导入与报告（执行）

首次执行按本阶段共有契约执行预检 → 导入 → 读回 → 计算 → 报告；返工先调用 get_rework_status。

## 需要解决的问题

- 记下预检得到的库名、分类、LCI 目录，把同一范围交给导入。
- 仅通过 MCP 调用 openLCA（禁止 bash/`uv run python` 直调 main）；慢库可在 `import_lci`、`get_model_graph` 等长工具上传 `timeout_sec`（≤7200，同时覆盖会话预算与单次 HTTP 读），勿用 shell `timeout` 包裹。
- 超时只查导入操作状态，不盲目重试写操作。范围若相对预检发生变化则停止。
- 保留 MCP 原始返回，写入 `workspace/outputs/reports/`。
- 报告须写前景清单与数据集映射两节，行能指回 BOM `item_id`。
- 部分失败、断链、空结果或资源未释放如实上报，不宣称通过。不要无界重试 `import_lci`。

## 返工方式

在原执行会话中根据审查意见返工：修正报告或按意见补做读回/计算（不得在范围变化后强行再导入）。重新提交最新报告与 handoff。

## 提交

handoff：`role=executor`，`status` 为 `ok` / `failed` / `blocked`，`artifacts` 含 `lca_report.md` 与原始结果路径。

确定性检查由主编排在本轮 handoff 后执行。可选用 `get_validation_state("report")` / `validate_artifacts("report")` 做提前反馈，不是提交 `ok` 的前提。只引用工具生成的检查，不自报权威校验计数。
