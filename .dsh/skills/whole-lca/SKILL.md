---
name: whole-lca
description: 通过 Python 主编排执行已有的 LCA 执行计划（workspace/inputs/plan.md）。
whenToUse: 用户要求运行 whole-lca 或从 plan.md 端到端生成 LCIA 报告时。
---

# Whole-LCA

不要把当前 DSH 会话当成主编排。运行：

```bash
uv run python src/scripts/lca_orchestrator/main.py --task whole-lca --worker dsh
```

编排步骤以 `harness/workflows/LCA-main.yaml` 为准。
