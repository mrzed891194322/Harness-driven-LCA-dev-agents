# 01 Whole-LCA 计划质量门禁规范

本规范只判断 `workspace/plan/execution_plan.md` 能否启动端到端执行，不要求同时存在或通过 `todo_list.md`。计划制定阶段的交付验收仍由计划制定规范管理。

## 1. 文件与版本

- 唯一输入为 `workspace/plan/execution_plan.md`，其同步来源固定为 `uploads/plan/execution_plan.md`。
- 文件必须是带 YAML front matter 的 Markdown，`template_kind` 必须为 `lca_execution_plan`。
- 当前仅接受 `template_version: 1` 或语义等价的字符串 `"1"`。缺失、格式非法或未知版本不得猜测，审查状态必须为 `needs_input`，记录迁移要求后结束本次运行；不得停下来请求确认。
- 必须保留执行计划模板中的 `## 1` 至 `## 6` 六个顶层章节；标题文字允许轻微措辞差异，但章节语义不得缺失。

## 2. 阻断性信息

下列内容必须在计划中给出确定值，不能作为自动检索缺口：

- 研究对象和研究目的；
- 功能单位的数值、基准流/功能描述和物理单位；
- 系统边界及纳入/排除的生命周期阶段；
- 截断规则或明确的“不采用截断”决定；
- 多产出是否存在，以及适用时的分配原则；
- 预期应用、结果解释范围和至少一种完成判断方式。

任一项缺失、仍为模板占位符、相互矛盾或无法唯一解释时，记录稳定 issue ID，保存 `reviews/plan-review.json`，将 manifest 置为 `needs_input` 并停止。

## 3. 可检索缺口

只有满足以下全部条件的缺口才可继续执行：

1. 在计划中明确标记，而不是隐含缺失；
2. 具有稳定 ID，格式为 `GAP-<大写字母或数字及连字符>`；
3. 标记 `gap_type: retrievable`；
4. 指明检索目标和允许的来源域（用户资料/RAG、openLCA 活动数据库，或二者）；
5. 缺口不改变第 2 节中的用户价值判断或目标范围。

典型可检索项包括背景 Process/Flow/Provider 候选、UUID、活动数据库中的 LCIA 方法、标准或用户资料中的已给定数据位置。检索不到时不得编造；将其转为未解决项，并根据影响置为 `needs_input` 或 `needs_review`。

## 4. 审查输出

计划审查必须使用 `harness/specs/public/references/schemas/review.schema.json`，`review_type` 为 `plan`、`attempt` 为 `1`。每个问题都必须包含 issue ID、严重度、规范引用、证据位置和可执行修正要求。

- `passed`：无阻断问题；允许的可检索缺口已逐项列出，可进入第 02 阶段。
- `needs_input`：存在阻断性缺失、非法格式或未知模板版本。
- `needs_review`：内容完整但存在需要人类判断且不适合自动检索的风险。
