# LCI 映射分流 · 04 reviewer

内容取舍统一按已注入的官方 PCFBench triage 英文口径。只读审核，不改产物，不代写另一套 triage。本档**无** triage MCP；须手检 checklist 与题面 picklist。

1. **读材料**：读取 executor 的 `workspace/runs/_run/notes/lci-triage-04/executor/checklist.json` 与 `artifacts/triage/triage.json`，并对照本题 `<plan>` 中的 Ecoinvent activities picklist。
2. **Axis A 幻觉闸**：核对 checklist 中每个 Axis A `candidates` 条目是否**逐字**出现在本题 picklist。任一不在清单 → `reject`（where=axis_a.candidates；problem=疑似幻觉或未核 picklist；expected=改为 picklist 内真实名或改 reasonable_direct_match）。
3. **FP 闸（挑战 should_map=true）**：若 rationale 几乎只有「单一/均质/可贸易/中间品」而 Axis A 候选空、牵强或 weak → reject，要求补 picklist 证据或改 false。对 packaging pair / speaker drivers、多供应源 market、功能油/粒料 proxy 等，强制书面回答「为何不必继续分解」（watch-outs：`triage-38569acde54f699a4d4999b3`、`triage-037d946ca7f7593a6a5d0e9e` 类机制）。
4. **FN 闸（挑战 should_map=false）**：若 false 主因是「无精确同名」或「听起来像配方/package」，但 picklist 存在同族/同功能 reasonable 活动且 MARKET 并非多部件装配 → reject，要求重评 Axis A。对名称含 package / additives / flux / catalyst / monomer 尤须执行（watch-outs：`triage-0e88100f9fbd8c90348abf52`、`triage-12033e3de9173e7c8ecb750f`、`triage-1f21d37bcc3fc0dcfc62dd1e` 类机制）。
5. **自洽与字段**：`should_map` 须与双轴 checklist + rationale 一致；rationale 非空且覆盖 A/B 各一句。`confidence≥0.8` **不能**单独作为 approve 依据。
6. **反馈与提交**：有可修问题就一次列全 `reject` issues（where / problem / expected）。核对完毕且无未解决问题 → `approve`。无法返工 → `terminate` 并说明原因。调用 `mcp__submit__submit`；reject 只传 verdict、issues 和可选 comment，不传 summary；不得 submit artifact。
