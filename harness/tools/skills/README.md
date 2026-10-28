# skills

每个技能一个目录：`skills/<名字>/SKILL.md`。agent 在节点 YAML 的 `tools.skills` 中列出才会拿到。

- 短名（如 `bom-claims-read`）解析为 `harness/tools/skills/<名>/SKILL.md`。
- 也可写**仓根相对路径**（含 `/` 或以 `.` 开头），指向 `…/SKILL.md` 或含 `SKILL.md` 的目录；宿主只把路径列进提示词，全文由模型按需 `read`。

## 评测最好 / 厚注入条件

| 技能 | 挂接 orch | 说明 |
| --- | --- | --- |
| `bom-claims-slim` | `bom-extract-02` / `03` executor | 薄约束：只交所问 / 禁多报 / 单位照抄 / 宁漏勿堆 |
| `bom-claims-review` | `bom-extract-03` / `04` reviewer | 审核：必须读长文；无支持→删；单位照抄；漏报高门槛才补 |
| `bom-claims-read` | `bom-extract-04` executor | 读文：ls→grep→offset/limit |
| `bom-claims-ops` | `bom-extract-04` executor | 单位 / 只交所问 / 交卷 |
| `bom-claims-best` | （无挂接） | **兼容别名**：正文只指向 read/ops/review |
| `lci-mapping-best` | `lci-mapping-04` | （本轮未拆） |
| `lci-triage-best` | `lci-triage-04` | （本轮未拆） |
