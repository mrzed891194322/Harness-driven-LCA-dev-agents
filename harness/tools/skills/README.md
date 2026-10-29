# skills

每个技能一个目录：`skills/<名字>/SKILL.md`。agent 在节点 YAML 的 `tools.skills` 中列出才会拿到。

- 短名（如 `bom-claims-flow`）解析为 `harness/tools/skills/<名>/SKILL.md`。
- 也可写**仓根相对路径**（含 `/` 或以 `.` 开头），指向 `…/SKILL.md` 或含 `SKILL.md` 的目录；宿主只把路径列进提示词，全文由模型按需 `read`。

## 评测技能

| 技能 | 挂接 orch | 说明 |
| --- | --- | --- |
| `bom-claims-flow` | `bom-extract-02` executor | 单技能工作流：提取→初稿→自检→改→交付；`refs/` 含读窗/类型黑名单/单位 |
| `bom-claims-slim` | （弃用） | 旧薄约束；勿挂接，改用 `bom-claims-flow` |
| `bom-claims-review` | `bom-extract-04` reviewer | 审核护栏（03 改靠专用 agent，不挂） |
| `bom-claims-read` | `bom-extract-04` executor | 读文：ls→grep→offset/limit |
| `bom-claims-ops` | `bom-extract-04` executor | 单位 / 只交所问 / 交卷 |
| `bom-claims-best` | （无挂接） | **兼容别名** |
| `lci-mapping-best` | `lci-mapping-04` | （本轮未拆） |
| `lci-triage-best` | `lci-triage-04` | （本轮未拆） |
