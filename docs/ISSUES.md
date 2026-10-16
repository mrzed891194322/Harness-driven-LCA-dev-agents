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
| 28 | 🟢 | `import_lci` 共享 1800s 会话预算，末次 Product System 请求读超时塌缩到亚秒（budget collapse）；超时后 IPC 挂死、预清理 openLCA 无超时 | `connection._TimeoutHTTPAdapter`、`guard.endpoint_guard`、`cleanup_service` | 分支 `refactor/p5-openlca-timeouts`：按请求读超时 + 预算不足 fail-fast；超时后健康探测、`openlca_unresponsive` 事件与诊断；清理同步超时；不确定状态下拒绝同名实体导入 |
| 29 | 🟢 | `partial_failure` 后同阶段重试被 `previous import requires reconciliation` 挡住，attempt 2/3 无法续导 Product System（`775710e3`） | `operations.import_request`、`workflow._execute_import` | 分支 `refactor/p5-import-resume`：`entity_plan` + `reconcile_import` / `resume_import` / `import_lci(resume_operation_id=...)`；显式 ProductSystem put 规避 `create/system` 挂死 |
| 30 | 🟢 | `endpoint_guard` 写入的 `.uncertain` 标记在 `import_request` 内被当成「上次超时遗留」，同 run 已成功导入的 UUID 触发 `uncertain_ipc_leftover_entities` / `openlca_unresponsive`（`9f97683e` attempt 4）；`resume_import` 又因 `lci_content` 变化报 `resume_identity_mismatch` | `guard.py`、`operations.import_request` / `resume_import_request`、`cleanup.py` | 分支 `refactor/p5-import-identity`：区分 guard 自有标记与真实遗留；同 run journal 实体可覆盖；scope/content 分拆 resume；预清理按 UUID 删 in-category 实体 |
| 31 | 🟢 | 预清理 openLCA 卡在 `endpoint busy: lock wait exceeded deadline`（`3d87884` 首轮）：`whole-lca` 先清 workspace 再清 openLCA，按 UUID 删除时 LCI/journal 已被删；清理持有 IPC 锁期间后端诊断等锁 5s 后误报「无法连接 / openLCA 未运行」；UUID 逐个 `get` 读超时被静默跳过、无重试 | `workspace_clean.CLEAN_PRESETS`、`diagnostics.check_openlca`、`cleanup.py` | 分支 `refactor/p5-cleanup-lock`：preset 改为 knowledge→openlca→workspace；诊断非阻塞探锁，被占用时报 `busy`「IPC 正被清理/导入占用」并带 holder（操作/PID/时长），状态页显示「占用中」；清理只读查询读超时→健康探测→重试 1 次，仍失败则中止并给出明确原因（不删除） |
| 33 | 🟢 | 后端重启后编排子进程已退出，`manifest.json` 仍显示 `running`，运行详情一直「运行中」（run `7b272327` @ 16:18） | `workflow_service.py`、`manifest.json`、`workflow_launch.py` | 分支 `refactor/p5-zombie-runs`：编排器心跳 + 启动/进度查询时 reconcile，标记 `interrupted` 并写 `run_interrupted` 事件；GUI 区分已中断/失败，支持从头重跑 |
| 32 | 🟢 | run `7b272327`：04 attempt 1 `import_lci` partial_failure，4 个 ProductSystem 在 explicit 连接阶段失败（no imported exchange）——前景 Process 按路径字母序导入，`c1-bottle-filling` 早于 `c1-plastic-components`，openLCA 静默丢弃尚未存在的 defaultProvider；03 attempt 2 试探性 `submit(process-mapping)` 不带 data 想原位重验被拒，随后重传 34 条 payload 时被 16:18 后端重启中断（run 终止的直接原因是重启，不是拒绝） | `workflow.load_lci_inventory` / `_execute_import`、`spec_mcp.submit`、openLCA 读工具 | 分支 `refactor/p5-cleanup-lock`：Process 拓扑排序 + 导入后 provider 修复；预检校验前景 provider 引用；`submit` 支持 `path`；读工具返回 `outside_project` + `project_scope`（project/background/uncategorized）；宿主 ProductSystem 统一写入 `target_category` |
| 34 | 🟢 | 2026-10-15 测试在主仓库运行时写入真实 workspace（`bbbbbbbb` manifest、`runs/standalone/`），且部分测试用 `BoundedIPCClient(8080)` 只靠 mock 挡住真实 openLCA；21:15 预清理 Process descriptors 卡 2 分钟、偶发 IPC 卡住后清理立即中止 | `src/tests/conftest.py`、`connection.BoundedIPCClient`、`lca_artifacts.store.Context.from_env`、`cleanup.read_with_retry` | 分支 `fix/test-isolation`：pytest 下 `BoundedIPCClient` 与 socket 拒连 8080/.env 端口，`OPENLCA_IPC_PORT` 指向无服务端口；`LCA_WORKSPACE`、`workspace_clean` 项目根与清理目标默认重定向到临时目录；`Context.from_env` 在 pytest 下缺 `LCA_WORKSPACE` 直接报错不回退；`test_resume_post_launches` 用临时项目根。预清理只读查询读超时后每 15 s 探测健康、最多 3 min，恢复后重试 1 次，否则中止。代码修改与测试一律在独立 worktree 进行 |
| 35 | 🟢 | run `5e2bbc4f` 02/03：模型连接掉线（每次调用 `stopReason=error`、`Connection error.`、0 token），pi SDK 自动重试 4 次后放弃但 `session.prompt()` 正常返回，回合被报成 `ok`，编排器记为“worker turn ended without handoff file”并消耗协议返工额度（03 两分钟内 1/3→3/3）；日志里看不到掉线 | `session_host.ts`、`turn_outcome.ts`、`pi_client/client.py`、`process.py`、`runner.run_sdk` | 分支 `fix/model-connection-failure`：以 SDK 原生事件 `auto_retry_end{success:false, finalError}` 为主信号（兜底：末条 assistant `stopReason` error/aborted 且错误像连接类），本轮无成功工具调用时返回 `status:error, kind:model_connection`，后端转成 `WorkerTransportError` 走原有 5 次退避重试、同会话恢复，不计协议返工；用尽后失败原因“worker 模型连接失败”。`_TRANSIENT_RUNTIME_ERROR` 补 `connection error` 等兜底 |
| 36 | 🟢 | 模型正常结束但本轮 0 工具调用、未交 handoff，直接计入协议返工 | `runner.run_sdk` | 同分支：同会话提醒继续并提交 handoff，最多 2 次（`WORKER_NUDGE_LIMIT`），独立计数，不计协议返工 |
| 37 | 🟢 | “额度 3/3 后又 prepare”：不是越界，上限=最多 3 次返工（共 4 轮），显示方式易误解；且掉线与真协议错误共用同一额度 | `runner._rework_invalid_handoff` | 语义不变，日志改为 `protocol rework 1/3 (剩余 2 次)`；连接重试与提醒均不计入 |
| 38 | 🟢 | 每轮 worker turn 无结构化记录；`pi-runtime.log` 只记连接开/关（单连接自 10:58 起不再写） | `runner._record_turn`、`inspect_run.py`、`agent-stream.tsx` | 同分支：每轮写 `worker_turn` 事件（stop_reason、error_kind=connection/timeout/429/5xx/none、error_message、input/output tokens、tool_calls、SDK retries、起止时间），backend.log 一行摘要；运行详情把“模型连接失败”显示为错误、与“agent 未交 handoff”分开；`npm run inspect` 按会话列出每轮 |
| 39 | 🟡 | run `8ab95ee0`：各阶段 `attempts.json` 里已结束的尝试仍是 `status=running`、`ended_at=null`，但 01、02 已有 `accepted.json`，结束时这两个字段没回写（不影响运行，影响续跑判断和 inspect） | 尝试记录的结束回写路径（待查） | 待处理，并入近期测试整理：attempt 结束（accepted/failed/rework）时回写 status 和 ended_at，加回归测试 |
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

## P5 Spec 三通道（长期关注：harness 核心问题）

分支 `refactor/p5-spec-channels`，设计见 `docs/REFACTOR_PLAN.md` §8B。自动测试通过，但还没在真实 LCA 里跑过。要持续跟踪的问题：

- **bash 绕过写保护**：path guard 只拦 write/edit。agent 用 bash 重定向（`cat > workspace/outputs/...`）还是能写正式路径。目前的兜底是：spec_mcp 用哈希把被改过的交付物标成 stale，`submit_handoff(ok)` 会被拒，编排器交卷后的检查也会拦下。要彻底堵住，需要在 bash 策略里解析重定向目标，或者把正式路径设成只读挂载。
- **writer=agent 的交付物**：03 的 LCI 目录、04 报告仍由 agent 直接写在正式位置，只做原位验收，因为它们是目录或多文件，并且由 MCP 工具生成。以后可以考虑改成先写草稿目录，由 spec_mcp 整体搬过去。
- **03 单位组检查依赖 provider 记录**：必须先在当前模型指纹上调用 `validate_providers_batch`，否则只能给出修法提示。以后可以让 spec_mcp 在 submit 时自己调用 openLCA 做验证，不再依赖 agent 攒证据。
- **spec_mcp 和 core 各有一份 spec 解析**：spec_mcp 不能 import core，所以 `spec_view.py` 是 core `view.py` 的镜像，靠测试保证两边输出一致。将来随 lca-tools 自包含项目一起收敛。
- **HMAC 密钥**：`.local/run/spec_mcp.key` 不在任何 agent 的读取范围内，但 bash 仍有可能读到。要确认 reviewer 和 worker 的 bash 策略不能访问 `.local/`。
- **旧运行的续跑**：spec 文件哈希和 `get_spec` 视图都进了指纹，P5 之前开始的运行不能在 P5 代码上续跑，只能重开。


## PR1：三层注入与权限收窄（2026-10-16）

| 问题 | 状态 | 处理 |
| --- | --- | --- |
| plain list replacement bypasses red lines | ✅ 已关闭 | `config/compose.py`：global 以下仅 `{add,remove}`，plain list 报 `E-COMPOSE-PLAIN-LIST`；`locked_rules` / `locked_rules_by_role` |
| assignment permissions can widen | ✅ 已关闭 | `permission_narrow.py`：ceiling（worker-default ∪ reviewer）→ stage → assignment 交集，扩权 `E-PERM-WIDEN` |
| plan autosave overwrote form on import | ✅ 已关闭 | `PUT /api/plan` 返回 410；计划路径由 workflow `plan:` 声明 |
| GUI 硬编码 workflow/阶段/角色表 | ✅ 已关闭（PR1c） | `preview-board`/`workflow-board`/`run-history` 等经 `GET /api/workflows` + manifest；启动任务 id 用 API `id` 字段 |
| 权限红线无专项回归 | ✅ 已关闭（PR1c） | `src/tests/t_core/agents/test_permission_narrow_redlines.py` |
| injection API 无层标记/写盘隔离测 | ✅ 已关闭（PR1c） | `src/tests/t_backend/test_harness_injection_api.py` |

## PR0：工作流本地副本与 `harness/.user` 收敛（2026-10-16）

- **已做（`feat/pr0-local-workflow-yaml`）**：默认 workflow 在 `harness/workflows/`；运行与编排读 `.local/harness/workflows/<name>.yaml`（首次启动复制，默认更新且本地未改时自动同步；`GET /api/diagnostics/environment` → `local_workflows`；`GET /api/harness/workflows/{name}/diff`、`POST …/restore-default`）。开跑快照仍写 `runs/_run/evidence/<run>/workflow.yaml`，`manifest.json` 增加 `workflow_snapshot`；同 run `--resume` 读快照而非当前 `.local`。
- **待收敛**：GUI/loader 仍用 `harness/.user/<rel>` 覆盖规则、spec、settings 等（REFACTOR_PLAN §8.5）。计划统一到 `.local/harness/` 同一棵 overlay（与 workflow 副本并列），**不迁移**现有 `.user` 内容，仅在新功能中逐步改解析入口并文档化；合并前需评估与 `harness/.user` 并存的 doctor/指纹行为。

## database_identity_verified 一直为 false

没有设置 `OPENLCA_DATABASE_NAME` 时，`database_identity_verified` 一直是 false，不影响运行。之后要么在 `.env` 里写明数据库名，要么让诊断里明确提示这一项。

## knowledge 里的用户文件不再进 git

`harness/knowledge/` 只保留各级 `README.md` 和 `.gitignore`。`main_plan.md`、`revise_plan.md`、`inputs/水瓶案例学习.md`，以及历史上放进该目录的手册和标准全文，已从版本库历史中移除。控制面板仍会在运行时写回计划和参考资料；`.gitignore` 的 `*` 让这些文件留在本地、不再被跟踪。已推送的远程历史还留着旧对象，需要强制推送才会从远端消失。

## read_artifact 误报 checksum mismatch（b71d2dd7，已修）

04 reviewer-1 用 `read_artifact` 读 `executor-1/raw/49078f9b…/raw.json` 时一直报 `artifact checksum mismatch`。文件本身没问题：宿主记录的 sha256（64 位）和文件字节一致，路径解析（reviewer 读 executor attempt）也正确。原因是 reviewer 手抄 sha 时漏了一个 `0`，传入的是 63 位（`…04a8a6b9b…`，正确为 `…04a8a06b9b…`），而工具对格式错误的 sha 也只报 mismatch，被误读成证据损坏。

修复：`store.normalize_sha256` 先校验传入值必须是 64 位十六进制（容忍大小写和首尾空白），否则报 `invalid sha256: expected 64 hex characters, got N`；格式正确但不一致时仍报 mismatch，并提示从 handoff/evidence manifest 原样复制。回归测试 `src/tests/t_harness/tools/lca_artifacts/test_read_artifact_checksum.py` 断言宿主 `ref()` 记录的 sha 能被 reviewer 的 `resolve_ref` 验证通过。

后续：`read_artifact` 支持只传路径。省略 `sha256` 时，工具在本轮 evidence manifest 的调用记录（同一路径以最后一次为准）、accepted 快照、文件所属 attempt 的 `handoff.json` 里查宿主为该路径记录的 sha，再按它校验文件；查不到就报 `no recorded sha256`，绝不跳过校验直接读。传了 `sha256` 时行为不变。`harness/rules/tools/` 已改为建议只传路径、不要手抄 sha。
