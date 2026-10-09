# AGENTS.md

本仓库用 Web 控制面板驱动一次完整 LCA。用户不通过 IDE 当主编排。接到指令时，先判断它落在下面这条闭环的哪一跳，只补那一跳，不要另起一套运行路径。

## 目标闭环

```
GUI 里的计划、资料、工作流
        │  POST /api/workflow/start
        ▼
FastAPI（src/backend）保存计划、清理上一次运行、拉起编排器
        │  uv run python src/scripts/workflow.py
        ▼
Python 编排器（src/backend/core/workflow）按 harness YAML 逐阶段派工
        │  NDJSON over .local/run/pi-runtime.sock：backend/pi_client → 项目唯一的 pi-runtime
        ▼
Pi SDK（src/pi-runtime，createAgentSession）
        │  progress.txt + manifest.json
        ▼
GUI「运行详情」流式渲染；「结果与历史」展示产物
```

这条链路还没有完全走通。改 GUI、启动、编排或展示时，用同一次运行把上下游对上，不要只改其中一层的内部格式。

## 接到指令时先定位

| 用户在说 | 先看 | 做到什么程度算接上 |
| --- | --- | --- |
| 计划、参考资料、工作流怎么配 | `src/frontend/web/app/plan/page.tsx`，`components/plan/` | 表单和资料写入 `harness/knowledge/plan/main_plan.md` 与 `harness/knowledge/inputs/`；执行时编排器读到的就是这份内容 |
| 点「执行LCA任务」没有开始，或跳转不对 | `components/plan/preview-board.tsx`，`POST /api/workflow/start`，`services/workflow_launch.py` | 按钮保存当前表单，后台启动 `whole-lca` 或 `revise-lca`，浏览器进入 `/runs` |
| 运行详情没有字，或清理阶段一直停在一句提示 | `GET /api/workflow/progress`，`services/workflow_service.py`，`workflow_launch.py` 的 `_consume` | 准备阶段的输出逐段出现；编排器写下 `progress.txt` 后，页面改显示该文件并保持追加 |
| Agent 正文、工具调用没有进终端 | `src/backend/core/agents/progress.py`，`src/backend/pi_client/process.py`，`pi-runtime/src/session_host.ts` | Pi 的 `turn.progress`（以及工具起止）写成 `progress.txt` 里已有的带标签文本，由 `/runs` 解析 |
| 跑完看不到报告或历史 | `src/frontend/web/app/results/page.tsx`，`workspace/outputs/`，`workspace/records/` | 结果页读本轮产物和 handoff，而不是只写死路径说明 |
| 模型、密钥、openLCA 不可用 | `/status`，`/api/diagnostics/environment`，设置里的模型档案 | 诊断与「预览执行」使用同一套就绪条件；未就绪时不要启动 |

工作流文件固定为 `harness/LCA-main.yaml`（新工作）和 `harness/LCA-revise.yaml`（修改工作），见 `services/workflow_cli.py` 的 `WORKFLOW_YAML_BY_TASK`。

## 已经接通的部分

- 控制面板页面：`/status` 环境诊断，`/plan` 计划、资料、编排预览，`/runs` 运行详情。正式入口是仓库根目录的 `npm start`（同步依赖、构建 pi-runtime 后执行 `npm run dev`；Next 默认 3000，API 默认 8800，Next 把 `/api/*` 代理到 FastAPI）。
- 「执行LCA任务」调用 `POST /api/workflow/start`，成功后 `router.push("/runs")`。
- `workflow_launch.py` 在清理前复制 `harness/knowledge/plan` 与 `inputs`，清理后写回，再用当前表单覆盖 `main_plan.md`（修订任务同时写 `revise_plan.md`），然后启动 `src/scripts/workflow.py`。`npm run dev` 默认使用真实模型并打印一行 `mode=real|mock`；`PI_RUNTIME_MOCK=1` 只给测试显式开启。
- 进程生命周期（ISSUES #23）：**整个项目只有一个 pi-runtime**。`npm start` / `npm run dev` 依次启动后端 → 立即启动 pi-runtime（`node src/pi-runtime/dist/main.js --listen .local/run/pi-runtime.sock`，`PI_RUNTIME_SOCKET` 可改路径）→ 前端，各自 `setsid` 常驻，pid 在 `.local/run/{backend,pi-runtime,web}.pid`，日志在 `.local/logs/{backend,pi-runtime,web}.log`。后端和每次运行的 `workflow.py` 都只连接这个套接字，**绝不自己起 runtime**；套接字不在时报 `pi-runtime 未运行，请用 npm run dev 启动`。会话和 MCP 仍按分工创建、按分工释放；运行结束（或 `workflow.py` 崩溃、连接断开）只释放该连接创建的会话，runtime 保持运行。`npm run stop` 的顺序：后端（lifespan 与编排子进程先释放各自会话）→ pi-runtime（SIGTERM，释放剩余会话、关闭 MCP、删除套接字）→ 前端，最后清理本仓库残留进程（`-- --dry-run` 只列出）。`npm run restart` = stop + start，stop 后若还有 runtime 就拒绝启动；`npm run dev` 发现已有 pid / 套接字 / runtime 进程也会拒绝。前台运行用 `npm run dev -- --foreground`，Ctrl-C 与 `npm run stop` 清理同一组进程。日常请用 `npm run stop`，不要靠 Ctrl-C。`PI_RUNTIME_PRIVATE=1` 只给测试，让客户端自起私有 stdio runtime；控制面板会忽略它。
- `/runs` 轮询 `GET /api/workflow/progress`。启动尚未写出新日志时，返回内存中的准备说明；新的 `workspace/records/logs/<run_id>/progress.txt` 出现后，整段换成该文件并继续按偏移追加。
- 终端渲染在 `components/runs/agent-stream.tsx`。它解析 `progress.py` 的标签行：编排器说明、`阶段(角色#次数)-pi-时间`、`→ 工具`、`✓` / `✗`、`error:` 和模型正文。历史日志 `workspace/records/logs/*/progress.txt` 就是目标样子。
- 编排器通过 `src/backend/pi_client/client.py`（连接见 `process.py` 的 `PiRuntimeClient`）以 NDJSON 调用项目唯一的 `src/pi-runtime` 服务；`runtime.info` 返回 pid、mode、连接与会话，`/status` 的诊断显示它。会话契约在 `src/backend/core/contracts/session_launch_spec.py`。

## 还没接通、用户让「走通」时优先补这里

1. **准备阶段的输出被吃掉。** `workflow_launch._consume` 只取清理和编排生成器的最终状态，清理脚本的逐行输出不会进入 `/runs`。用户会长时间只看到「正在保存当前计划，并清理上一次运行…」。要把生成器里的新文本写进 launch 缓冲，让 `progress` 能追加。
2. **Pi 的流式事件没有写成进度日志。** `session_host.ts` 会 `emitEvent("turn.progress")`，`process.py` 能挂 `add_event_handler`，但正式 `run_turn` 没有把文本和工具调用交给 `progress.print_session`。`print_session`、`format_tool_start`、`format_assistant` 目前没有调用方。接上之后，`/runs` 不用改解析格式。
3. **`services/file_sync.py` 的 `sync_files` 是空操作。** 不要依赖 `executor_console.run_pre_workflow_console` 里的 sync 把 GUI 上传写回磁盘。现在能保住资料，是因为 launch 自己做了快照和恢复。若改清理顺序，必须继续保证 `inputs/` 和计划文件在编排器启动前还在。
4. **编排画布只读。** `workflow-board.tsx` 只 `GET /api/harness/document`。画布上的修改不会写回 `harness/LCA-*.yaml`，执行仍用磁盘上的原文件。用户要求「按 GUI 里的工作流跑」时，要先定义保存位置，再让 `--workflow` 指向那份文件。
5. **结果页是占位。** `app/results/page.tsx` 只提示目录。报告在 `workspace/outputs/`，交接在 `workspace/records/handoffs/`，运行摘要在 `workspace/records/manifest.json`。
6. **计划表单没有逐字自动保存。** 只有点击执行时，启动流程才把表单写入 `main_plan.md`。执行前进程若中断，磁盘上的计划可能仍是旧的。

## 改动约束

- 业务入口只放在 `src/backend/api/app.py`。编排逻辑放在 `src/backend/core`，api、services 只做适配，由 `src/scripts/workflow.py` 作为子进程入口。不要在 Next.js 里直接调 Pi，也不要再加一套并行的启动脚本。
- 清理预设 `whole-lca` 会清 knowledge 暂存、`workspace` 生成物和 openLCA。改启动流程时先复制用户资料再清理，失败也要写回。没有用户明确要求时，不要替用户点「执行LCA任务」。
- 界面文案用中文。运行详情保持与计划页相同的整页卡片（`status-fit`、`plan-board`、`settings-card`），终端按阶段、工具行和正文渲染，不要退回整段 JSON。
- 进度文本继续用 `progress.py` 的标签格式。改解析或渲染时，用现有 `progress.txt` 对照，避免页面和日志各说一种方言。
- 密钥只在设置流里写入 `.local/credentials/`。不要把密钥抄进进度日志、handoff 或提交。

## 验证

- Python：`uv run pytest src/tests/t_backend/test_workflow_launch.py src/tests/t_backend/test_workflow_progress.py`
- 前端类型：`npx tsc --noEmit -p src/frontend/web/tsconfig.json`
- 改了页面或启动按钮时，在已运行的控制面板里走一遍：计划预览 → 执行（仅当用户要求真的开跑）→ 运行详情能看到新增文本。只改渲染时，用已有 `progress.txt` 即可，不必再开一轮会清工作区的运行。
