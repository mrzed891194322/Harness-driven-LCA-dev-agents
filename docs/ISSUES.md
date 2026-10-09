# 问题清单（LCA 跑通阶段）

状态：🔴 未修 / 🟡 进行中 / 🟢 已修（未提交）/ ✅ 已提交
维护：Grok Bot；群内报的问题都收在这里。更新于 2026-10-09 23:13（运行 3dfd5066… 于 22:38 全部 4 个阶段通过）

## 执行链路（后端 / pi-runtime）

| # | 状态 | 问题 | 位置 | 备注 |
|---|---|---|---|---|
| 1 | ✅ | `run_sdk` 在 `assignment` 赋值前使用 | `src/shared/core/workflow/execution/runner.py` | 已随 21:34 commit |
| 2 | 🟢 | SessionLaunchSpec 键不一致，且 `ProviderDispatcher` 不转交 `attach_launch_spec` | `runner.py`, `pi_agents/client.py`, `SessionConfig` | 改为 `config.launch_spec` |
| 3 | 🟢 | 01 reviewer 无交卷工具（`mcp: []`，写权限被剥离） | `LCA-main.yaml`, `LCA-revise.yaml`, `launch_spec.py` | 绑定 `lca_artifacts.submit_handoff` |
| 4 | 🟢 | Pi 会话文件写到 `~/.pi`，`run_turn` 每轮新建会话 | `session_host.ts` | 改 `SessionManager.open(session_file)` 并复用 |
| 5 | 🟢 | 所有 runtime 错误都被当作连接错误重试 5 次 | `pi_agents/process.py` | 只重试网络/超时/429/5xx |
| 6 | 🟢 | 关闭 TLS 校验 | `executor_console.py` | 两行已删 |
| 7 | 🟢 | `mcp.json` 写在会话目录但 SDK 只读全局目录 | `session_host.ts` | `createMcpExtension({loadConfig})` |
| 8 | 🟢 | 工具白名单仍是旧名 `mcp`/`mcpScript` | `permissions.py`, `launch_spec.py` | 改 `mcp__<server>__*` |
| 9 | 🟢 | 返工提示仍要求“写入 handoff_path” | `prompt_build.py`, `handoff.py`, `runner.py` | 改为调用 `submit_handoff` |
| 10 | 🟢 | 未调用 `session.bindExtensions()`，MCP 扩展不发 `session_start`，工具静默缺失 | `session_host.ts` | doctor 需检查会话实际工具 |
| 11 | 🟢 | pi-runtime stderr 是无人读取的管道，可能卡死子进程 | `pi_agents/process.py` | 落盘 `.local/logs/pi-runtime.log` |
| 12 | 🟢 | 后端日志写在会被清理的 `workspace/tmp` | 启动脚本 | 改 `.local/logs/backend.log` |
| 13 | 🔴 | whole-lca 预清理删除 `workspace/records/**`、`workspace/tmp/**`，上一轮证据全丢 | `workspace_clean.py:41` | 运行记录迁到 `.local/runs/<run_id>/` |
| 14 | 🔴 | `src/scripts/dev.mjs` 默认 `PI_RUNTIME_MOCK=1` | `src/scripts/dev.mjs` | 建议默认关闭，待 Du Yuan 确认 |
| 15 | 🔴 | 后端/前端随启动它的 shell 退出 | 启动方式 | 临时用 `setsid`；需正式的常驻启动方式 |
| 16 | 🔴 | 沙箱路径 `UV_CACHE_DIR=/tmp/cursor-sandbox-cache/...` 漏进 worker `mcp.json` | 环境继承 | 需白名单式传环境变量 |
| 17 | 🔴 | 同一份 prompt 同时作为 system 和 user 发送，token 翻倍 | runner / session_host | 见重构方案 P2 |
| 19 | 🟢 | MCP 超时单位错：秒→毫秒后 Pi 又按秒乘 1000，溢出成 1 ms，`control_openlca` 初始化即超时，12 个工具未注册 | `launch_spec.py:155`, `session_host.ts`, SDK `extensions/mcp/runtime.js:159-160` | `mcp.json` 改写秒；`.local/logs/pi-runtime.log` 有 `TimeoutOverflowWarning` |
| 20 | 🟢 | MCP 服务连接失败无报错，worker 调工具时才发现 | `session_host.ts` | 会话启动时最多等 90 秒校验每个服务已注册工具，否则报“MCP 服务未就绪” |
| 21 | 🟢 | 工具缺失等基础设施失败仍按 executor 返工重试 3 次 | runner 重试分类 | “MCP 服务未就绪”不在重试名单 |
| 22 | 🔴 | 会话结束后 `control_openlca` 的 MCP 子进程不退出，一次运行残留 6 个 `workflow_mcp.py` | `session_host.ts` 会话关闭 / MCP 扩展 | 会话结束需关闭 MCP 连接；doctor 检查残留进程 |
| 18 | 🔴 | `test_plan_form` 失败（解析 `main_plan.md` 的 CML 条件） | `src/tests` | 与 plan 文件内容有关 |

## 前端（GUI）

| # | 状态 | 问题 | 备注 |
|---|---|---|---|
| F1 | 🔴 | 后端挂掉时页面显示 `Unexpected token 'I'... is not valid JSON` | 识别 500/连不上，提示“后端未连接” |
| F2 | 🔴 | 后端重启后计划和参考资料丢失 | 计划状态需持久化 |
| F3 | 🔴 | 编排页各阶段显示“快速模型 · 本地 Ollama”，与预览页默认模型不一致 | 需显示实际生效的模型 |
| F4 | 🔴 | 运行失败后预览页不提示 | 预览页显示上次运行结果 |
| F5 | 🟢 | 看不到 agent 的流式输出（工具调用、完成了什么） | Pi 会话事件需经后端推到 `/runs`，见方案 P1 |
| F6 | 🔴 | 失败原因整段原文直接铺在页面上，没有排版 | 按错误码/摘要/详情折叠展示 |
