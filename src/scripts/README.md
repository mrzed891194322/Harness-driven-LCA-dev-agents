# scripts

- **`start.mjs`**：正式入口（`npm start` / `node src/scripts/start.mjs`）。同步 uv / Node 依赖、构建 pi-runtime，再执行 `npm run dev`；多余参数传给 dev（如 `npm start -- --foreground`）。
- **`dev.mjs`**：`npm run dev` 依次启动 FastAPI 后端 → **立即**启动项目唯一的 pi-runtime 服务（`--listen .local/run/pi-runtime.sock`，`PI_RUNTIME_SOCKET` 可改；环境变量与原来给 MCP 的白名单相同，由 `python -m backend.pi_client.env` 计算）并等它应答 `runtime.info` → Next.js 前端。默认真实模型，启动时打印 `mode=real|mock`（只有显式 `PI_RUNTIME_MOCK=1` 才是 mock，仅供测试）。默认 detached（setsid）：关掉终端也不会退出，pid 在 `.local/run/{backend,pi-runtime,web}.pid`，输出在 `.local/logs/{backend,pi-runtime,web}.log`，全部就绪后返回。已有 pid、套接字有人监听或本仓库已有 pi-runtime 进程时拒绝启动。`npm run dev -- --foreground` 保持前台并输出日志，Ctrl-C 按与 `npm run stop` 相同的顺序清理同一组进程。需要 Unix 域套接字（Linux / macOS / WSL）。
- **`stop.mjs`**：`npm run stop` 依次停止后端（进程组 SIGTERM：lifespan 与编排子进程先释放各自会话）→ pi-runtime（只给主进程发 SIGTERM，由它释放全部会话、关闭 MCP、删除套接字）→ 前端，各 15 秒后 SIGKILL；再清理本仓库残留的编排、后端、pi-runtime、Next、MCP 进程，并删除失效的套接字文件。`npm run stop -- --dry-run` 只列出不动手。
- **`restart.mjs`**：`npm run restart` = stop + start；stop 后若仍有 pi-runtime 就拒绝启动，保证不叠出第二个。
- **`stop_lib.mjs`**：stop / restart / 前台 Ctrl-C 共用的停止逻辑。
- **`service_files.mjs`**：共用的 pid / 日志 / 套接字路径与工具函数。
- **环境引导**：`proj_init/`（首次仓库准备）。
- **编排器内部入口**：`workflow.py`、`clean.py`、`check_status.py` 供控制面板后端 / 测试 / 引导子进程调用，**不是**面向用户的控制方式。
- **`gitee_upload/`**：发布辅助，与 LCA 控制无关。

业务 HTTP 在 `src/backend/api/`；编排逻辑在 `src/backend/core/`。用户操作一律走 Web 控制面板。
