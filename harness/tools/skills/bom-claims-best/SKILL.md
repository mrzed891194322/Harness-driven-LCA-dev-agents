# BOM 数量抽取 · 兼容别名（已拆分）

本技能已拆成短技能，请改读：

- `harness/tools/skills/bom-claims-flow/SKILL.md` — 02 executor 工作流；**04** executor 亦挂 flow（无 check MCP）
- `harness/tools/skills/bom-claims-review/SKILL.md` — 审核（**04** reviewer + MCP `bom_claims_check`；03 用专用 agent、不挂）
- `harness/tools/skills/bom-claims-read/SKILL.md` — 读文（档内保留；**04 不挂**）
- `harness/tools/skills/bom-claims-ops/SKILL.md` — 单位 / 只交所问 / 交卷（档内保留；**04 不挂**）

`bom-extract-02` 挂 `bom-claims-flow`；`bom-extract-03` **不挂技能**（专用 agent 三件套）；`bom-extract-04` = **orch 三件套** + flow（executor）+ review（reviewer + check MCP）。本目录仅旧名兼容。
