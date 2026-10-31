# BOM 数量抽取 · 02 工作流

按序执行，不扩写。

1. **读技能与题面**：读本技能与题面（plan/query）。
2. **定目标/条数**：只依题面列短清单，每项「对象×所问指标」；清单条数即 N（`expected_count`）。不依原文或其他来源增删清单。
3. **读原文并抽取**：按清单在 `harness/knowledge/inputs/` 用 `grep` 定位、`read` 确认，写 `workspace/artifacts/bom/claims.json`。每条有 `claim_id`；`value` 照原文数值与正负号；`unit` 照抄证据中的完整单位短语；`evidence` 写文件名+位置并逐字摘录含该数与单位的原文，只能推断时以 `[推断]` 开头并写依据。
4. **核对**：调用 `check_claims(checklist=[清单项...])`，同时查数量（条数 vs N）与正确性（value/unit 在 evidence、evidence 在原文）。工具只提醒，不删改、不拦交卷。
5. **交付**：交卷前若有告警，回到对应步骤（清单→2，抽取/证据→3）改**该条**，再核对；最多 2 轮核对。仍剩的告警在 `submit` 说明里逐条写一句保留理由，然后 `submit`。勿按告警批量删条。原文完全无可答数字才 `abstained: true` + `claims: []`。

有 `<rework>` 时只改所列问题后再交付。
