# LCI 映射分流 · 04 executor

内容取舍统一按已注入的官方 PCFBench triage 英文口径；本技能只规定执行顺序与双轴 checklist。只 triage 题面 **MARKET**，ROOT MATERIAL CONTEXT 仅作解释。

1. **写 checklist（先于 triage.json）**：在 `workspace/runs/_run/notes/lci-triage-04/executor/checklist.json` 写入双轴记录，形状示例：
   ```json
   {
     "axis_a": {
       "candidates": ["exact picklist name 1", "..."],
       "reasonable_direct_match": "yes|no",
       "reason": "one sentence"
     },
     "axis_b": {
       "must_decompose_first": "yes|no",
       "reason": "one sentence"
     },
     "decision_preview": true
   }
   ```
   - **Axis A · list-matchability**：在本题 `Ecoinvent activities` 段内标出 ≤3 个**逐字存在于 picklist** 的候选活动名（禁止凭记忆编造清单外名字）。判定 `reasonable_direct_match` 为 yes/no 并各写一句依据。无精确同名 ≠ 自动 no；须问是否仍有 reasonable 直接映射（专打无同名就 abstain 的 FN）。有近义/同族命中也不等于一定 yes——还须过 Axis B（专打 proxy 过度映射 FP）。
   - **Axis B · complexity**：回答是否必须先拆成子组件才能映射：多材料装配、多功能 package、未定化学族捆绑、多工艺路线聚合 → 倾向 must_decompose_first=yes；单一可贸易中间品且 Axis A=yes → 倾向 no。名称含 packaging/package/additive/flux/catalyst/monomer **不**自动等于必须拆——若 Axis A 已有 reasonable 活动则仍可 map（专打过度分解 FN）。主打「单一/均质/可贸易」 alone 不足以 yes（专打 FP_overconfident_atomicity）。
   - `decision_preview`：按下方合成规则得到的布尔预览（与将写入的 `should_map` 一致）。
2. **读题面**：完整阅读 MARKET 描述与 picklist；ROOT 只帮助理解 MARKET，不对 ROOT 做 triage 决策。
3. **写产物**：写入指定 `triage.json`。合成规则：**仅当** Axis A 为 yes **且** Axis B 为可直接映射（must_decompose_first=no）→ `should_map=true`；否则 false。`rationale` 必须**各用一句话**覆盖 Axis A 与 Axis B（防单轴叙事）。可选 `confidence` / `candidate_name`；不得把 confidence 当作理由。不得查询 openLCA。
4. **自查并结束**：核对 rationale 不与 `should_map` 矛盾（勿出现「应分解」却 true，或「可直接映射」却 false）。不要调用 submit；结束本回合。
5. **返工**：只按 reviewer issues 修改 checklist 与 triage；在笔记中记录已改的轴或依据。

**机制向 watch-outs（勿背金标答案）**：过度映射叙事常见于 bulk commodity / proxy 油粒料 / 多供应源 market（例 id：`triage-037d946ca7f7593a6a5d0e9e`、`triage-07be09d3525a5405b3f9f3f7`、`triage-38569acde54f699a4d4999b3`）。过度分解常见于 additives package / flux / 专用 monomer（例 id：`triage-0e88100f9fbd8c90348abf52`、`triage-12033e3de9173e7c8ecb750f`、`triage-1f21d37bcc3fc0dcfc62dd1e`）。
