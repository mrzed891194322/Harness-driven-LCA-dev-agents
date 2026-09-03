---
name: revise-lca
description: 通过 Python 主编排从 revise.md 启动可追溯修订。
whenToUse: 用户要求运行 revise-lca 时。
---

# Revise-LCA

不要把当前 DSH 会话当成主编排。运行：

```bash
uv run python src/scripts/lca_orchestrator/main.py --task revise-lca --worker dsh
```

编排步骤以 `harness/workflows/LCA-revise.yaml` 为准。
