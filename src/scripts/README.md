# scripts

- **`start.mjs`**：用户入口。同步 uv / Node 依赖后执行 `npm run dev`（`node src/scripts/start.mjs`）。
- **`dev.mjs`**：`npm run dev` 同时启动 FastAPI 与 Next.js 控制面板。默认真实模型，启动时打印 `mode=real|mock`（只有显式设置 `PI_RUNTIME_MOCK=1` 才是 mock，仅供测试）。Linux/macOS 下默认 detached（setsid）：关掉启动它的终端也不会退出，pid 写在 `.local/run/{backend,web}.pid`，输出在 `.local/logs/{backend,web}.log`，等健康检查通过后返回。`npm run dev -- --foreground` 保持前台，Ctrl-C 停止（Windows 总是前台）。
- **`stop.mjs`**：`npm run stop` 按 pid 文件向进程组发 SIGTERM（15 秒后 SIGKILL），再清理本仓库残留的 pi-runtime、MCP、编排子进程、后端与 Next 进程；`npm run stop -- --dry-run` 只列出不动手。
- **`service_files.mjs`**：上面两个脚本共用的 pid / 日志路径与工具函数。
- **环境引导**：`proj_init/`（首次仓库准备）。
- **编排器内部入口**：`workflow.py`、`clean.py`、`check_status.py` 供控制面板后端 / 测试 / 引导子进程调用，**不是**面向用户的控制方式。
- **`gitee_upload/`**：发布辅助，与 LCA 控制无关。

业务 HTTP 在 `src/backend/api/`；编排逻辑在 `src/backend/core/`。用户操作一律走 Web 控制面板。
