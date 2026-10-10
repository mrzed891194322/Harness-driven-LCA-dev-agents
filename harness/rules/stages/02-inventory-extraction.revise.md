# 02 修订补充契约

本文件只在 `revise-lca` 注入，同时约束本阶段 reviser 与 reviewer。

## 额外输入

- `harness/knowledge/plan/revise_plan.md`
- 上一轮 BOM JSON 与 Markdown（若缺失，按意见与资料重建完整 BOM，并在缺口中说明）

## 修订要求

- 产出仍是完整 canonical BOM，字段同共有契约。
- 未受影响且仍适用的行保留；点名增删改及其关联数量、合计、情景和缺口说明同步更新并回链 `revise_plan.md`。
- 不得因落实用户意图而编造数量或静默丢弃未读文件标记。

## 审查补充

先判用户意见是否落实，再判计划覆盖、回链与未读标记等正确性。方法正确但未落实 `revise_plan.md` 不得 `passed`。因落实意见而偏离原计划不得失败。`fix_instructions` 先写意图缺口（意见原文与对应 `item_id`），再写正确性缺口。
