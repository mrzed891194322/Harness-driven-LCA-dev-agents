# Whole-LCA 公共运行说明

本目录只说明四步工作流共用的路径、阶段顺序、handoff 和终止态。阶段做什么见对应编号包；不要在这里加 JSON Schema 或确定性校验脚本。

1. `references/workflow-runtime-spec.md`：路径、阶段循环、会话与 handoff、`completed` / `failed`
2. `references/templates/checklist.md`：可选人读清单
3. `references/examples/`：薄 `manifest.json` 与审查笔记示例
4. `references/evidence-contract.md`：v2 证据、校验状态和同 run 阶段返工复用契约；实现放 tools，不在 spec 中放业务脚本。
