---
id: 04-openlca-reporting
inputs:
  - workspace/outputs/LCI/
  - workspace/outputs/inventory/extracted-bom.json
  - workspace/outputs/inventory/process-mapping.json
outputs:
  - workspace/outputs/reports/lca_report.md
---

# 04 openLCA 建模与报告

预检、导入、读回、LCIA 并写出最终报告。执行后审查，最多 3 轮。工具写库失败则停止，不要无界重试 `import_lci`。

## 阶段目标

在审查通过的 LCI 上完成导入与计算，按模板写出面向用户的中文报告。

## 输入说明

- 已通过审查的 `workspace/outputs/LCI/`
- BOM 与 mapping，用于报告回溯
- 报告提纲：`references/templates/lca_report.md`

## 提交要求

首次执行按顺序：

1. `preflight_import_lci`。记下库名、分类、LCI 目录，把同一范围交给导入。
2. `import_lci(request_id=稳定请求ID, preflight_id=本次预检ID)`，再 `get_model_graph`。首次导入可用默认预算或 `timeout_sec=7200`；**禁止** bash/`uv run python` 直调 `control_openlca` main。MCP/IPC 超时只查 `get_import_operation`，openLCA 可能仍在慢速链接。超时只查导入操作状态，不盲目重试写操作。范围若相对预检发生变化则停止。
3. `calculate_product_system`。完整结果由工具直接写入本 run 的 raw 目录，保留返回的路径与 SHA-256。
4. 按模板写 `workspace/outputs/reports/lca_report.md`，并写前景清单与数据集映射两节，行能指回 BOM `item_id`。

MCP 报错、空结果或资源未释放时如实返回，不得标完成。

## 验收标准

- 最终报告可读，面向用户的说明为中文。
- 数值能指到 `workspace/outputs/reports/` 中的 MCP 原始返回。
- 限制节包含地域代理等留档决定。
- 前景清单与数据集映射两节能指回 BOM `item_id`。
- 工具报错、空结果或资源未释放不得通过。

审查通过后运行 `completed`。

## 前置及停止条件

范围变化、导入失败或三次审查失败则 `failed`，须非空 `status_reason`。

## 机器证据

写者提交前不必调用 `validate_artifacts`。主编排在合法 `ok` 且产物齐全后运行 `profile="report"` 检查；失败则返工写者。handoff 可引用 checks_ref.path 和 evidence_manifest_ref。reviewer 独立核对证据并决定通过，不把工具成功当作阶段通过。检查定义见公共 `references/evidence-contract.md`；旧检查输入变化即 stale。

## 计算计划与返工

首次计算前写 `reports/calculation-plan.json`：`{"calculations":[{"product_system":"正式查询的UUID","impact_method":"正式查询的UUID","amount":1.0}]}`。必须覆盖全部声明的 Product System；可选 allocation、regionalized、costs、parameters 默认与计算接口相同。同一 Product System+方法在本版计划中唯一；不同情景使用不同 Product System。查询和计算参数必须与计划一致。

从模板写报告叙述并保留三组 lca 标记，随后调用 render_report_tables 生成表格。不得手工修改生成区数值。报告正文中的额外数值和语言仍由 reviewer 核对。

attempt>1 先调用 get_rework_status，判定 report_only 时仅重新生成/核对报告，不调用 health/preflight/import/graph/calculate。计算计划变化而已审 LCI 未变时，确认目标并重算相关结果；工具/证据丢失时按具体缺口补做，不误标 report_only。BOM、mapping、LCI 或计划相对已审核快照变化则停止并说明需要上游审查，不在 04 强行重导入。
