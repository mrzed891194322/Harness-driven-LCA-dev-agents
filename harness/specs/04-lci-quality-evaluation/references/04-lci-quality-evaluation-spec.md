# 04 Whole-LCA LCI 质量评估规范

## 1. 审查依据

- 审查依据包括计划目标、第 02 阶段检索证据、项目 LCI 建模规范、JSON 模板和映射报告模板。
- 每轮审查前必须运行第 03 阶段的确定性 LCI 校验；校验失败直接形成稳定 `LCI-FORMAT-*` issue，不得以人工可读性替代机器契约。
- Reviewer 必须核对每个 exchange 的 `isInput` 是显式布尔值，且不得使用 `input` 别名；任一缺失、`null` 或非布尔值均为阻断问题。
- 比较情景必须核对 auto-link 拓扑中的前景输入 `defaultProvider`、Provider 输出 Flow、`expectedProcessIds`、背景 Provider flow 与地域证据；只检查 JSON 字段存在不足以通过。
- Reviewer 必须复算映射报告中的单位转换；缺少 kg→tonne 等换算因子说明时记录 `LCI-MAP-FORMULA-*`，即使实体数值碰巧正确也不得忽略。
- 审查结果必须遵守 `harness/specs/public/references/schemas/review.schema.json`，`review_type` 为 `lci`。
- Reviewer 只读，不得修改 LCI 或生成替代产物。

## 2. 问题追踪

- 每个问题使用跨轮次稳定的 `LCI-...` issue ID，并记录严重度、精确规范引用、证据位置、修正要求和状态。
- 修正不得重命名仍未解决的问题；已关闭问题再次出现时保留原关联。
- 每轮审查固定保存为 `reviews/lci-review-<attempt>.json`，不得覆盖历史记录。

## 3. 审查循环

- 最多执行 3 次 LCI 审查，attempt 依次为 1、2、3。
- attempt 1 或 2 未通过：只把仍未解决的问题和受影响产物委托给执行 Agent 定向修正，再进入下一次审查。
- attempt 3 未通过：不得进行第 4 次修正或审查；保存问题，manifest 置为 `needs_review` 并停止。
- 只有 review 状态为 `passed` 且无 `critical` 或 `major` 未解决问题时，才能进入第 05 阶段。
