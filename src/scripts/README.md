# scripts

- **`start.mjs`**：用户入口。同步 uv / Node 依赖后执行 `npm run dev`（`node src/scripts/start.mjs`）。
- **`dev.mjs`**：`npm run dev` 同时启动 FastAPI 与 Next.js 控制面板。
- **环境引导**：`proj_init/`（首次仓库准备）。
- **编排器内部入口**：`workflow.py`、`clean.py`、`check_status.py` 供控制面板后端 / 测试 / 引导子进程调用，**不是**面向用户的控制方式。
- **`gitee_upload/`**：发布辅助，与 LCA 控制无关。

业务 HTTP 在 `src/backend/api/`；编排逻辑在 `src/backend/core/`。用户操作一律走 Web 控制面板。
