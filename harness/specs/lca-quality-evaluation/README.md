# LCA Quality Evaluation Specification Index

本目录是 whole-lca 运行质量评估的唯一契约来源。Codex agent 和 skill 只负责执行，不得复制或改写评分语义。

## References

1. `references/evaluation_spec.md`：输入、适用性、评分、状态和输出规则。
2. `references/rubric.json`：固定且版本化的检查项、维度和产物覆盖矩阵。
3. `references/schemas/lca-quality-score.schema.json`：结构化评分结果 schema。
4. `references/templates/lca_quality_report.md`：由 JSON 确定性渲染的 Markdown 结构。

## 规范配套脚本

- `references/scripts/contract.py`：rubric 与评分 JSON 的确定性契约校验和 Markdown 渲染。
- `references/scripts/cli.py`：校验与渲染命令入口。
- `references/scripts/tests/`：评分契约和渲染脚本的附属回归测试。
- 测试命令：`uv run python -m unittest discover -s harness/specs/lca-quality-evaluation/references/scripts/tests -v`。

这些脚本只实现本规范定义的规则，不得自行扩展评分语义。

## 变更耦合

whole-lca 的必需产物、schema、模板、状态语义或路径发生变化时，必须在同一变更中更新 rubric 的 `artifact_coverage`、受影响检查项、输出 schema/模板与回归夹具。未知 workflow contract 版本不得猜测为兼容。
