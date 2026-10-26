# skills

每个技能一个目录：`skills/<名字>/SKILL.md`。agent 在节点 YAML 的 `tools.skills` 中列出才会拿到。

- 短名（如 `bom-claims-best`）解析为 `harness/tools/skills/<名>/SKILL.md`。
- 也可写**仓根相对路径**（含 `/` 或以 `.` 开头），指向 `…/SKILL.md` 或含 `SKILL.md` 的目录；宿主只把路径列进提示词，全文由模型按需 `read`。

## 评测最好条件（04 档）

| 技能 | 挂接 orch |
| --- | --- |
| `bom-claims-best` | `bom-extract-04` |
| `lci-mapping-best` | `lci-mapping-04` |
| `lci-triage-best` | `lci-triage-04` |
