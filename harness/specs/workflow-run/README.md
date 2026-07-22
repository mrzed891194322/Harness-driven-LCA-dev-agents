# Whole-LCA Workflow Run Specification Index

本目录是 `whole-lca` 端到端工作流的共享产物契约。OpenCode 与 Codex 的 `workflow-main` 只负责平台适配，不得复制或改写这里的 schema。

## References

1. **计划接收门禁**
   - `references/plan_intake_spec.md`
2. **状态机、日志、审查与交接**
   - `references/workflow_run_spec.md`
3. **导入、模型图、LCIA 结果与报告**
   - `references/lcia_results_spec.md`
4. **JSON Schema**
   - `references/schemas/workflow-manifest.schema.json`
   - `references/schemas/stage.schema.json`
   - `references/schemas/review.schema.json`
   - `references/schemas/handoff.schema.json`
   - `references/schemas/import-report.schema.json`
   - `references/schemas/model-graph.schema.json`
   - `references/schemas/raw-lcia-results.schema.json`
   - `references/schemas/calculation-manifest.schema.json`
5. **报告模板**
   - `references/templates/lca_report.md`

## 规范配套脚本

- `references/scripts/validation.py`：计划接收门禁和 LCI 审查循环的确定性校验。
- `references/scripts/tests/`：脚本及本规范契约的附属回归测试。
- 测试命令：`uv run python -m unittest discover -s harness/specs/workflow-run/references/scripts/tests -v`。

这些脚本只实现本规范明确规定的确定性规则，不是独立规范来源。

## 质量评估同步规则

修改本工作流的必需产物、schema、模板、状态语义或交付路径时，必须在同一变更中更新 `../lca-quality-evaluation/` 的固定产物覆盖矩阵、受影响 rubric、score schema/Markdown 模板和回归夹具。不得让新交付物在质量评估中静默漏评。
