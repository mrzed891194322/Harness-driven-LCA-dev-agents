# Whole-LCA 公共契约索引

本目录保存 `whole-lca` 各阶段共同使用的运行、状态、证据和产物格式契约。阶段规范位于 `harness/specs/01-*` 至 `harness/specs/07-*`；公共目录不代表独立业务阶段。

## References

1. **运行、状态与证据**
   - `references/workflow-runtime-spec.md`
2. **JSON Schema**
   - `references/schemas/workflow-manifest.schema.json`
   - `references/schemas/stage.schema.json`
   - `references/schemas/review.schema.json`
   - `references/schemas/handoff.schema.json`
   - `references/schemas/import-report.schema.json`
   - `references/schemas/model-graph.schema.json`
   - `references/schemas/raw-lcia-results.schema.json`
   - `references/schemas/calculation-manifest.schema.json`
3. **报告模板**
   - `references/templates/lca_report.md`

## 公共脚本

- `references/scripts/validation.py`：计划接收门禁和 LCI 审查循环的确定性校验。
- `references/scripts/tests/`：公共脚本、schema、阶段路由和平台配置的回归测试。
- 测试命令：`uv run python -m unittest discover -s harness/specs/public/references/scripts/tests -v`。

脚本只实现阶段规范明确规定的确定性规则，不是独立规范来源。

## 质量评估同步规则

修改必需产物、schema、模板、状态语义或交付路径时，必须在同一变更中更新 `.codex/specs/lca-quality-evaluation/` 的固定产物覆盖矩阵、受影响 rubric、score schema、Markdown 模板和回归夹具。不得让新交付物在质量评估中静默漏评。
