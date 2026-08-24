---
description: 从已审核执行计划启动带审查、范围预检、openLCA 自动导入读回和 LCIA 结果归档的无人值守端到端 LCA 工作流
---

**任务执行**：

- 执行下列脚本清理 openLCA 与 workspace 生成文件（如有）：
   `uv run python harness/tools/control_openlca/cleanup_output/main.py --yes`
   `uv run python src/scripts/clean_dir/main.py --yes --target workspace_without_inputs`

- 读取并执行 `harness/workflows/LCA-main.md` 定义的 LCA 完整工作流，将 `workspace/inputs/plan.md` 作为唯一计划输入，并按该工作流及其引用的共享 spec 执行；

- 工作流返回后，保留 `workspace/memory/`、`workspace/outputs/LCI/` 和 `workspace/outputs/reports/` 中的固定产物并立即结束当前会话。
