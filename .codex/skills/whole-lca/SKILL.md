---
name: whole-lca
description: 通过 Python 主编排执行已有的 LCA 执行计划（plan.md）。
---

# Whole-LCA

不要把当前 Codex 会话当成主编排。运行：

```bash
uv run python src/scripts/lca_orchestrator/main.py --task whole-lca --worker codex
```

编排步骤以 `harness/workflows/LCA-main.yaml` 为准。GUI 或用户已前置 `clean_dir --preset whole-lca`。
