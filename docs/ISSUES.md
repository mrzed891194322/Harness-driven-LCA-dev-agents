# 问题清单（LCA 跑通阶段）

状态：🔴 未修 / 🟡 进行中 / 🟢 已修（未提交）/ ✅ 已提交
维护：Grok Bot；群内报的问题都收在这里。更新于 2026-10-10 09:08（P1 验证全部通过；已切到 `refactor/p1-single-runtime` 重跑中）

## 执行链路（后端 / pi-runtime）

| # | 状态 | 问题 | 位置 | 备注 |
|---|---|---|---|---|
| 1 | ✅ | `run_sdk` 在 `assignment` 赋值前使用 | `src/backend/core/workflow/execution/runner.py` | 已随 21:34 commit |
| 2 | 🟢 | SessionLaunchSpec 键不一致，且 `ProviderDispatcher` 不转交 `attach_launch_spec` | `runner.py`, `backend/pi_client/client.py`, `SessionConfig` | 改为 `config.launch_spec` |
| 3 | 🟢 | 01 reviewer 无交卷工具（`mcp: []`，写权限被剥离） | `LCA-main.yaml`, `LCA-revise.yaml`, `launch_spec.py` | 绑定 `lca_artifacts.submit_handoff` |
| 4 | 🟢 | Pi 会话文件写到 `~/.pi`，`run_turn` 每轮新建会话 | `session_host.ts` | 改 `SessionManager.open(session_file)` 并复用 |
| 5 | 🟢 | 所有 runtime 错误都被当作连接错误重试 5 次 | `backend/pi_client/process.py` | 只重试网络/超时/429/5xx |
| 6 | 🟢 | 关闭 TLS 校验 | `executor_console.py` | 两行已删 |
| 7 | 🟢 | `mcp.json` 写在会话目录但 SDK 只读全局目录 | `session_host.ts` | `createMcpExtension({loadConfig})` |
| 8 | 🟢 | 工具白名单仍是旧名 `mcp`/`mcpScript` | `permissions.py`, `launch_spec.py` | 改 `mcp__<server>__*` |
| 9 | 🟢 | 返工提示仍要求“写入 handoff_path” | `prompt_build.py`, `handoff.py`, `runner.py` | 改为调用 `submit_handoff` |
| 10 | 🟢 | 未调用 `session.bindExtensions()`，MCP 扩展不发 `session_start`，工具静默缺失 | `session_host.ts` | doctor 需检查会话实际工具 |
| 11 | 🟢 | pi-runtime stderr 是无人读取的管道，可能卡死子进程 | `backend/pi_client/process.py` | 落盘 `.local/logs/pi-runtime.log` |
| 12 | 🟢 | 后端日志写在会被清理的 `workspace/tmp` | 启动脚本 | 改 `.local/logs/backend.log` |
| 13 | 🔴 | whole-lca 预清理删除 `workspace/records/**`、`workspace/tmp/**`，上一轮证据全丢 | `src/backend/services/workspace_clean.py:41` | 运行记录迁到 `.local/runs/<run_id>/` |
| 14 | 🟢 P1 `5b89231` | `src/scripts/dev.mjs` 默认 `PI_RUNTIME_MOCK=1` | `src/scripts/dev.mjs` | 建议默认关闭，待 Du Yuan 确认 |
| 15 | 🟢 P1 `5b89231` | 后端/前端随启动它的 shell 退出 | 启动方式 | 临时用 `setsid`；需正式的常驻启动方式 |
| 16 | 🟢 P1 `5b89231` | 沙箱路径 `UV_CACHE_DIR=/tmp/cursor-sandbox-cache/...` 漏进 worker `mcp.json` | 环境继承 | 需白名单式传环境变量 |
| 17 | 🔴 | 同一份 prompt 同时作为 system 和 user 发送，token 翻倍 | runner / session_host | 见重构方案 P2 |
| 19 | 🟢 | MCP 超时单位错：秒→毫秒后 Pi 又按秒乘 1000，溢出成 1 ms，`control_openlca` 初始化即超时，12 个工具未注册 | `launch_spec.py:155`, `session_host.ts`, SDK `extensions/mcp/runtime.js:159-160` | `mcp.json` 改写秒；`.local/logs/pi-runtime.log` 有 `TimeoutOverflowWarning` |
| 20 | 🟢 | MCP 服务连接失败无报错，worker 调工具时才发现 | `session_host.ts` | 会话启动时最多等 90 秒校验每个服务已注册工具，否则报“MCP 服务未就绪” |
| 21 | 🟢 | 工具缺失等基础设施失败仍按 executor 返工重试 3 次 | runner 重试分类 | “MCP 服务未就绪”不在重试名单 |
| 22 | 🟢 P1 `5b89231` | 会话结束后 MCP 子进程不释放：一次运行（01–04）残留 15 个（6 个 `workflow_mcp.py` + 9 个 `lca_artifacts`），已手动清理 | `src/backend/pi_client/process.py` 的 `shutdown()` 无调用方；pi-runtime `protocol.ts:26` 未处理 stdin close；会话释放时可能未关 MCP 连接 | 编排结束调用 shutdown；runtime stdin 关闭即退出；会话 dispose 关闭 MCP；doctor 检查残留 |
| 23 | 🟢 P1 `5b89231` | 同一时刻存在两个 pi-runtime（后端起一个、编排器又起一个），后者成孤儿被 systemd 收养 | `src/backend/pi_client/process.py` `shared_runtime()` 调用方 | 查清是谁多起了一个，保证每个后端进程只有一个 runtime |
| 24 | 🔴 | 同一粒料流同时是 `granulate_rer` 和 `granulate_row` 的参考输出；`components_*` 先于 `granulate_*` 导入，openLCA `PREFER_DEFAULTS` 未采用 exchange 的 defaultProvider，Case 2/3（`e3e3dde3`、`2173ad5b`、`cff02c8b`）全部连到 RER 粒料 `a11da816`，缺中国代理粒料 `650ffb1c` | 03 LCI 设计 / 导入顺序 / 建产品系统的 provider 链接策略 | 每个情景用不同产品流或显式 provider 链接；导入后校验关键节点 |
| 25 | 🔴 | 04 发现上游 LCI 问题时无法退回 03：未写 `calculation-plan.json`，`get_rework_status` 返回 eligible=false | 返工判定逻辑 / `control_openlca` | 返工资格不应依赖下游计划文件；支持跨阶段回退并带原因 |
| 26 | 🔴 | 01 reviewer 读取 `workspace/records/handoffs` 和 evidence 下 `manifest.json` 时路径不存在（2 个工具报错） | 01 提示词 / 工作区初始化 | 预建目录或在提示中说明首阶段无历史 |
| 27 | 🔴 | worker 读取范围过宽：会去读 `docs/`（如 `docs/dev/history/.../bottle_filling_case1.json`）。要求只能读 `workspace/` 和 `harness/knowledge/`，其余 harness 内容由宿主提前注入 | 当前白名单只限工具名不限路径；`read`/`bash` 无路径约束 | 权限规则加读写路径范围，由 Pi 拦截扩展执行；bash 可绕过，reviewer 不给 bash |
| 18 | 🟢 P1 `5b89231` | `test_plan_form` 失败（解析 `main_plan.md` 的 CML 条件） | `src/tests` | 与 plan 文件内容有关 |

## 前端（GUI）

| # | 状态 | 问题 | 备注 |
|---|---|---|---|
| F1 | ✅ 已验证 | 后端挂掉时页面显示 `Unexpected token 'I'... is not valid JSON` | 识别 500/连不上，提示“后端未连接” |
| F2 | 🔴 | 后端重启后计划和参考资料丢失 | 计划状态需持久化 |
| F3 | 🔴 | 编排页各阶段显示“快速模型 · 本地 Ollama”，与预览页默认模型不一致 | 需显示实际生效的模型 |
| F4 | 🔴 | 运行失败后预览页不提示 | 预览页显示上次运行结果 |
| F5 | 🟢 | 看不到 agent 的流式输出（工具调用、完成了什么） | Pi 会话事件需经后端推到 `/runs`，见方案 P1 |
| F6 | 🔴 | 失败原因整段原文直接铺在页面上，没有排版 | 按错误码/摘要/详情折叠展示 |
| F7 | 🔴 | “后端未连接”提示里写 `npm run dev`，应改为 `npm start` / `node src/scripts/start.mjs` | |
| F8 | 🔴 | 同一条“后端未连接”提示在一个页面重复多遍（状态页 3 遍，计划、运行页各 2 遍） | 只保留顶部横幅 |
| F9 | 🔴 | 后端断开时状态页“LCA 工具”显示“诊断未加载”，说法不统一；“开始LCA”按钮仍可点击 | 统一文案；断开时禁用按钮 |

## 案例 3 结果比原文偏高约 11%（建模精度，长期跟踪）

运行 `d18bc463`（2026-10-10）中，案例 3 主情景是 764.47 kg CO2-Eq，原文是 686。运输单位修正之前，反推的结果约 739，已经偏高 7.7%，所以不是单位换算的 bug。可能的原因有：背景数据库版本（这里用的是 ecoinvent 3.11）、provider 的选取、LCIA 方法版本。下一步按贡献逐段拆开，和原文 Figure 23 对比（运输段原文是 474 kg）。这件事不阻塞分支合并。

