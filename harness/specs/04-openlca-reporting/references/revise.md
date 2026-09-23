# 04 修订补充契约

本文件只在 `revise-lca` 注入，同时约束本阶段 reviser 与 reviewer。

## 额外输入

- `workspace/inputs/revise.md`
- 上一轮 `workspace/outputs/reports/lca_report.md` 及其 raw 结果（若仍存在）

## 修订要求

- 覆盖 `workspace/outputs/reports/lca_report.md`，不得只改摘要而丢掉共有契约要求的章节。
- 在共有模板 §7 声明边界后追加 `references/templates/revision-report-sections.md`：§8 本轮修订摘要、§9 用户意见落实矩阵、§10 与上一轮结果的差异。
- §9 必须覆盖 `revise.md` 中每条可执行意见；`REV-*` 指向 BOM `item_id`、mapping 行或分析证据。共有需求落实表仍覆盖未被修订的原计划要求。
- §10 每个数值差异回链新旧 raw 结果路径；比较前核对功能单位、范围与方法是否一致，无法比较时说明原因，不得推断环境优势。

## 审查补充

矩阵与 `revise.md` 逐条对应优先于文风或章节完整度：意见未落实不得 `passed`。因落实意见而相对原报告改写模型或数值不得失败，但数值仍须能指到本轮 MCP 原始返回。工具报错、空结果或资源未释放仍不得通过。`fix_instructions` 先写未落实的意见与 `REV-*`，再写缺失章节或原始文件。

新 revise 的第一次执行不复用上一 run 的检查通过状态或 raw 计算；仅同一 revise run 内 attempt>1 适用共有返工复用规则。
