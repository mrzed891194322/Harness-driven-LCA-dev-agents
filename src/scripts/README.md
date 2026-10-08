# scripts

- **`dev.mjs`**：`pnpm dev` 同时启动 FastAPI 与 Next.js。
- **Python 薄 CLI**：`workflow.py`、`clean.py`、`check_status.py`、`proj_init/`、`gitee_upload/`（均依赖 `src/shared` + `src/backend` 的 path 引导）。

业务 HTTP 在 `src/backend/api/`；共用逻辑在 `src/shared/`。
