# 04 导入与报告修订（执行）

新 revise run 首次按本阶段共有契约执行预检 → 导入 → 读回 → 计算 → 覆盖报告；同 run 返工先调用 get_rework_status。不要覆盖 `plan.md`。

## 需要解决的问题

- 同时读取本轮已通过的 LCI、BOM、mapping、`revise.md` 与上一轮 `workspace/outputs/reports/lca_report.md`（及其中引用的 raw 结果，若仍可读）。
- 记下预检得到的库名、分类、LCI 目录，把同一范围交给导入。范围相对预检变化则停止。
- 保留工具直接写入本 run 的 raw 引用，不手工复制完整响应。
- 覆盖写出完整 `lca_report.md`：保留模板既有章节，并追加 `references/templates/revision-report-sections.md` 的三节。落实矩阵用 `REV-*`，可指向 BOM `item_id` 或 mapping 行。与上一轮的数值差异必须回链新旧 raw 路径，无法比较时说明原因，不得推断环境优势。
- 部分失败、断链、空结果或资源未释放如实上报。不要无界重试 `import_lci`。

## 返工方式

在原修订会话中根据审查意见返工：先补用户意见落实缺口，再修正报告或按意见补做读回/计算（不得在范围变化后强行再导入）。重新提交最新报告与 handoff。

## 提交

handoff：`role=reviser`，`status` 为 `ok` / `failed` / `blocked`，`artifacts` 含 `lca_report.md` 与原始结果路径。

确定性检查由主编排在本轮 handoff 后执行。可选用 `get_validation_state("report")` / `validate_artifacts("report")` 做提前反馈，不是提交 `ok` 的前提。只引用工具生成的检查，不自报权威校验计数。
