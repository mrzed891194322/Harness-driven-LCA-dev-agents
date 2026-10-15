# 已经接通

改这些路径时保持现有行为，只补缺口，不要换一种内部格式。

- 控制面板页面：`/status` 环境诊断，`/plan` 计划、资料、编排预览，`/runs` 运行详情。正式入口是仓库根目录的 `npm start`（同步依赖、构建 pi-runtime 后执行 `npm run dev`；Next 默认 3000，API 默认 8800，Next 把 `/api/*` 代理到 FastAPI）。进程命令只按 `.agents/skills/proj-ops/references/process.md`。
- 「执行LCA任务」调用 `POST /api/workflow/start`，成功后 `router.push("/runs")`。
- `workflow_launch.py` 在清理前复制 `harness/knowledge/plan` 与 `inputs`，清理后写回，再用当前表单覆盖 `main_plan.md`（修订任务同时写 `revise_plan.md`），然后启动 `src/scripts/workflow.py`。`npm run dev` 默认使用真实模型并打印一行 `mode=real|mock`；`PI_RUNTIME_MOCK=1` 只给测试显式开启。
- 整个项目只有一个 pi-runtime。`npm start` / `npm run dev` 依次启动后端、pi-runtime（`node src/pi-runtime/dist/main.js --listen .local/run/pi-runtime.sock`，`PI_RUNTIME_SOCKET` 可改路径）、前端。pid 在 `.local/run/{backend,pi-runtime,web}.pid`，日志在 `.local/logs/{backend,pi-runtime,web}.log`。后端和每次运行的 `workflow.py` 都只连接这个套接字，不自己起 runtime；套接字不在时报 `pi-runtime 未运行，请用 npm run dev 启动`。运行结束只释放该连接创建的会话。`PI_RUNTIME_PRIVATE=1` 只给测试。Windows 使用 `.local/run/pi-runtime.endpoint` 里的本机 TCP 地址。
- `/runs` 轮询 `GET /api/workflow/progress`。启动尚未写出新日志时，返回内存中的准备说明；新的 `workspace/runs/_run/progress.txt` 出现后，整段换成该文件并继续按偏移追加。
- 终端渲染在 `components/runs/agent-stream.tsx`。它解析 `progress.py` 的标签行：编排器说明、`阶段(角色#次数)-pi-时间`、`→ 工具`、`✓` / `✗`、`error:` 和模型正文。历史日志在 `.local/runs/<run_id>/` 与 `workspace/runs/_run/progress.txt`。
- 编排器通过 `src/backend/pi_client/client.py`（连接见 `process.py` 的 `PiRuntimeClient`）以 NDJSON 调用项目唯一的 `src/pi-runtime`。`runtime.info` 返回 pid、mode、连接与会话。会话契约在 `src/backend/core/contracts/session_launch_spec.py`。
