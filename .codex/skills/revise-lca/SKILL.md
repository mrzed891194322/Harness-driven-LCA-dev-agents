---
name: revise-lca
description: 通过 Python 主编排从 revise.md 启动可追溯修订。
---

# Revise-LCA

不要把当前 Codex 会话当成主编排。运行：

```bash
uv run python src/scripts/lca_orchestrator/main.py --task revise-lca --worker codex
```

编排步骤以 `harness/workflows/LCA-revise.yaml` 为准。GUI 或用户已前置 `clean_dir --preset revise-lca`。
