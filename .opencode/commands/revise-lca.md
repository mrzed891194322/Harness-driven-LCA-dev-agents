---
description: 通过 Python 主编排无人值守执行 revise-lca
---

**任务执行**：

整次运行由 Python 主编排驱动，不要把当前会话当成主编排。

```bash
uv run python src/scripts/lca_orchestrator/main.py --task revise-lca
```

GUI 或用户须已完成 `clean_dir --preset revise-lca`，意见在 `workspace/inputs/revise.md`。
