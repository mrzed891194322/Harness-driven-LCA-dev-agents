# LCA 质量评价入口

LCA 质量评价已经转为 Codex Agent 专用、机器可校验的契约：

- 评价规则：[`.codex/specs/lca-quality-evaluation/references/evaluation_spec.md`](../../../.codex/specs/lca-quality-evaluation/references/evaluation_spec.md)
- 固定检查项与产物覆盖：[`.codex/specs/lca-quality-evaluation/references/rubric.json`](../../../.codex/specs/lca-quality-evaluation/references/rubric.json)
- JSON Schema：[`.codex/specs/lca-quality-evaluation/references/schemas/lca-quality-score.schema.json`](../../../.codex/specs/lca-quality-evaluation/references/schemas/lca-quality-score.schema.json)
- Markdown 模板：[`.codex/specs/lca-quality-evaluation/references/templates/lca_quality_report.md`](../../../.codex/specs/lca-quality-evaluation/references/templates/lca_quality_report.md)

本目录的 benchmark 使用同一 rubric，不再维护第二份条款清单。水瓶 Case 1/2/3 默认是内部教学与开发回归，不是拟向公众披露的比较声明；`PUB-*` 只有在用途证据明确改变后才适用。

修改 whole-lca 的必需产物、schema、模板、状态语义或路径时，必须在同一变更中更新正式评价契约及其测试。自动评价是项目质量治理，不构成 ISO 认证、正式符合性认证或独立关键审查。
