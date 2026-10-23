# 文档目录重组（2026-10-23）

Du Yuan 批准；删除整棵 `docs/dev/`；现行文档不再放在 `docs/refactor/v5/`。

`docs/archive/` 仅本机保留、**整目录 gitignore，不进版本库**。

| 原路径 | 新路径 |
|--------|--------|
| `docs/refactor/v5/DESIGN.md` 等设计文 | `docs/architecture/` |
| `docs/refactor/WORKFLOW_DESIGN.md` | `docs/architecture/WORKFLOW_DESIGN.md` |
| `docs/refactor/v5/{ISSUES,SERVE_DEV}.md` | `docs/ops/` |
| `docs/TODO.md` | `docs/ops/TODO.md` |
| `docs/tutorial/**` | `docs/guide/tutorial/` |
| `docs/lang_CN/**` | `docs/guide/lang_CN/` |
| 根目录旧 `REFACTOR_PLAN` / `ARTIFACTS` / `ISSUES` / `PROJECT_LAYOUT` | `docs/archive/` |
| `docs/refactor/pi-*.md`、`v5/{COMMIT_PLAN,SIMPLIFY_PLAN}.md` | `docs/archive/` |
| `docs/dev/**` | **已删除** |

布局权威：`docs/architecture/DESIGN.md`（勿再把 `archive/PROJECT_LAYOUT.md` 当现行说明）。
