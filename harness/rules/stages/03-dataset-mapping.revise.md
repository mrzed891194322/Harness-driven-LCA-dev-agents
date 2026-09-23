# 03 修订补充契约

本文件只在 `revise-lca` 注入，同时约束本阶段 reviser 与 reviewer。

## 额外输入

- `workspace/inputs/revise.md`
- 上一轮 process-mapping.json 与 LCI 目录

## 修订要求

- 必须写出完整 canonical LCI，不得只提交相对上一轮的差分文件。
- 受 `revise.md` 影响的已有背景实体必须重新正式核查；新建前景 UUID 按映射规则生成，仍适用的前景实体保持标识稳定。同步受影响的数量换算、情景和说明，不得留下与现行要求矛盾的旧实体。
- 审查通过前仍禁止 `import_lci`。

## 审查补充

先判 mapping / LCI 是否落实用户意见，再判功能对应、地域理由与 UUID 可追溯性。方法正确但未落实 `revise.md` 不得 `passed`。因落实意见而更换数据集（且查询真实）不得因偏离原映射而失败。明显错配或臆造 UUID 仍 `failed`。`fix_instructions` 先写意图缺口，再写要改的 `item_id`、JSON-LD 文件或 UUID。
