# skills

每个技能一个目录：`skills/<名字>/SKILL.md`。agent 在节点 YAML 的 `tools.skills` 中列出才会拿到。

- 短名（如 `bom-claims-flow`）解析为 `harness/tools/skills/<名>/SKILL.md`。
- 也可写**仓根相对路径**（含 `/` 或以 `.` 开头），指向 `…/SKILL.md` 或含 `SKILL.md` 的目录；宿主只把路径列进提示词，全文由模型按需 `read`。

## 评测技能

| 技能 | 挂接 orch | 说明 |
| --- | --- | --- |
| `bom-claims-flow` | `bom-extract-02` executor；`bom-extract-04` executor | r21 单文件工作流（定清单→读文→claims→核对循环→交付）；04 executor **无** check MCP |
| `bom-claims-slim` | （弃用） | 旧薄约束；勿挂接，改用 `bom-claims-flow` |
| `bom-claims-review` | `bom-extract-04` reviewer | 先 MCP `check_claims` 再对照长文；多报/范围外/单位类须 reject（03 专用 agent，不挂） |
| `bom-claims-read` | （档内保留；04 不挂） | 读文：ls→grep→offset/limit |
| `bom-claims-ops` | （档内保留；04 不挂） | 单位 / 只交所问 / 交卷 |
| `bom-claims-best` | （无挂接） | **兼容别名** |
| `lci-mapping-best` | `lci-mapping-04` | （本轮未拆） |
| `lci-triage-flow-04` | `lci-triage-04` executor | 写 triage 前双轴 checklist → 合成 should_map |
| `lci-triage-review` | `lci-triage-04` reviewer | 手检 picklist 逐字 + FP/FN 闸；无 MCP |
| `lci-triage-best` | （无挂接） | 兼容保留；04 已改 flow/review 分挂 |
