# harness v5 最小版本：9 个提交（与 harness-v5-design-draft-v2 对齐）

分支 `refactor/harness-v5-minimal`，从 master `da96ab1` 拉出；worktree 放在 `.local/wt/202606-harness-agent-LCA`（目录名与 openLCA 分类一致；.local 已被 gitignore）。测试只用临时目录，不碰真实 workspace、.local 或 openLCA；不推送，不合并。

## 贯穿原则
- **宿主 3 把锁优先实现**，任何配置都改不了：①计划只读且永远可读；②只能写 produces 对应的 artifacts 子目录 + 本节点 `runs/<节点>/`；③openLCA 增删改只在 `202606-harness-agent-LCA`（常量）。
- **日志原则**：开跑/加锁/节点开始与结束/requires 失败/审核结论/计划导入、保存与解析/模型鉴权预检，每条都带时间写入 `runs/_run/events.jsonl` 和后端日志；鉴权错误直接致命。
- 取消 settings.yaml，改为固定的中文语言规则；不注入 AGENTS.md（关掉 pi 自动加载，使用项目专用 agentDir）。
- spec 不支持用户定制，GUI 只能整套选择。

## 提交
**C1 文档与目录骨架**
- 目标：写 docs/refactor/V5_DESIGN.md；harness/ 只留 rules/{global,roles/<角色>/{prompt.md,access.yaml}}、specs/<交付>/{spec.md,schema.json,checks.yaml}、knowledge/（扁平）、tools/{mcp,skills}、workflows/{*.yaml,nodes/}。v5 代码放在新包 `src/backend/v5/`，旧代码暂不动。
- 测试：t_v5/test_layout（只能有这 5 个目录、knowledge 无子目录）。
- 验收：测试通过，旧测试不受影响。

**C2 配置模型**
- 目标：`v5/config.py`（pydantic）解析 workflow、node（requires/produces/inject/agents/flow/accept）、角色、spec。flow 是有向图：edges 由 from/on/to 组成，必须能到达 done 或 failed，含 max_rounds；v1 只支持 executor + reviewer；结论 pass/reject/stop。
- 测试：解析通过；未知节点、到不了终点、重复边、未知角色都报错。

**C3 宿主锁与权限**
- 目标：`v5/access.py` 计算 默认（只读）+ 角色 access.yaml + 节点覆盖 + 3 把锁；`OPENLCA_PROJECT_CATEGORY` 常量放进 control_openlca 共享模块并替换现有 3 处推导；pi-runtime 新增 tool_call 拦截（read/write/edit/bash 的路径都检查），拦截写日志。
- 测试：锁不可覆盖、produces 授予写权限、越界读写被拦；pi-runtime 拦截单测。

**C4 线性执行器 + 逐节点续跑**
- 目标：`v5/runner.py`。开跑先清空 workspace，再生成计划；对每个节点：检查 requires（为空、缺失或解析失败直接报错）→ 执行者会话 → 宿主 checks → 审核者会话 → 读固定 `submit` 的结论 → 按流程图走，受 max_rounds 限制。反馈写 `runs/<节点>/feedback/round_N.md`。状态写 `runs/<节点>/status.json` 和 `runs/_run/manifest.json`。续跑：已通过的节点跳过，中途停的节点清空本节点目录和 produces 后整体重跑。用 agent_settled（含 aborted）判断结束并写日志。
- 测试：用 scripted session 覆盖 pass、reject→pass、超轮、stop、requires 缺失、续跑跳过/重跑。

**C5 注入**
- 目标：`v5/inject.py` 按顺序组装：global 规则（含知识库读取说明、中文规则）→ 角色 prompt.md → 工具/技能清单 → `<plan>`（全文）+ `<inputs>`（路径+简述）→ `<deliverable_X>`（spec.md + 从 schema 生成的摘要）→ `<rework>`（第 2 轮起）。权限不进提示词。
- 测试：prompt 快照（新写，替代 golden）。

**C6 pi 会话接入**
- 目标：pi-runtime 支持 v5 launch：noContextFiles、项目 agentDir、inMemory settings、skillsOverride、显式 tools、model+thinkingLevel；MCP 用 createMcpExtension（direct 暴露）+ bindExtensions，首轮前做工具就绪预检；固定 `submit` 工具；先写一个续跑工具恢复测试；模型鉴权预检（失败即致命）。
- 测试：pi-runtime 单测（注入顺序、无 AGENTS.md、submit、拦截、预检）。

**C7 删除旧编排**
- 目标：v5 接管 `/api/workflow/start`；删除 01、LCA-revise、spec_mcp、host_action、旧 resume（只删旧实现）、golden、config_fingerprint、settings.yaml、旧 prompts/permissions；计划改到 artifacts/plan/（revise_plan 一起），knowledge 扁平化；tools/shared 并入 mcp。
- 测试：pytest、pi 测试、tsc 全绿；旧测试只删除对应部分。

**C8 示例节点与验收**
- 目标：nodes/write-paragraph、summarize；workflows/demo-*.yaml；LCA 节点 bom、mapping、report（对应原 02–04）拼成 full-lca.yaml。
- 测试（集成，用假模型）：两个节点跑通；调换顺序跑通；删掉一个跑通；删掉前置产物立即报错；停止后续跑（已通过节点跳过）。

**C9 GUI 最简版**
- 目标：/plan 保留用户填写表单（开跑时写 artifacts/plan/main_plan.md）；工作流下拉 `data-testid="workflow-select"`；开始按钮 `run-start`；/runs 页节点表 `node-table`、`node-row-<id>`（带 data-status）、`node-error-<id>`、`run-status`；节点详情可按轮次看反馈。agent 卡片只读显示 模型+思考深度 / 角色 / 权限 / 工具 / 规则，spec 挂在节点层。
- 测试：API 测试 + tsc；GUI 端到端由 模拟操作员 做。

## 完成标准
9 个提交全部通过测试后先汇报，不切换服务；之后由 Grok Bot 协调重启，在 v5 上跑一次完整 4 阶段 LCA，GWP 与基线一致（Case1 223.67 / Case2 790.09 / Case3 787.93 / Case3-S 786.58）才算完成。

## Progress log

- C7a (done): `backend/v5/service.py` (V5Service: start/stop/resume/status/events/feedback in one thread);
  `POST /api/workflow/start` and `/stop` now run v5 (`workflow` + `plan`, or the old form fields rendered into the plan;
  `task` whole-lca → full-lca). New: `POST /api/v5/resume`, `GET /api/v5/workflows|status|events`,
  `GET /api/v5/nodes/{node}/feedback/{round}`. Model auth preflight runs inside the run lock, logged as `model_preflight`.
- C7b (pending, needs scope decision): deleting the old engine. Import-graph check: plan_form, diagnostics_service,
  pi_client.client still import backend.core.workflow/*, so removal is ~20k lines across core/agents, core/runtime,
  core/workflow, services and ~40 test modules, not a few files.
- C7b (done, option b): the old engine is detached from the run path. `/api/workflow/start|stop` run v5; the old
  from-stage resume (`/api/workflow/resume`, `resume-preview`) is disabled (410 / not eligible) in favour of
  `POST /api/v5/resume`. Old engine code still reachable from the plan form, diagnostics and the old pi client stays;
  its full deletion (01, LCA-revise, spec_mcp, host_action, old resume, golden, config_fingerprint, settings.yaml,
  old prompts/permissions) is a separate commit after C8, C9 and the real LCA run.
- C7c (done): old engine fully deleted. Backend: `backend/core/workflow/**`, old `core/agents` (session, injection,
  activity, progress, providers, transcript, probe/run, permission_narrow, …), `core/runtime` except `model_profiles`,
  `pi_client/client.py`, services `workflow_service`, `session_snapshots`, `prompt_templates`, `spec_service`,
  `local_workflows`, `harness_browser`, `injection_view`, `run_reconcile`, `workflow_launch`, `resume_plan`,
  `orchestrator_wiring`, `openlca_attempt_cleanup`, `executor_console`, `file_sync`, `workflow_cli`, `workflow_manifest`.
  Routes removed (no 410 kept, the frontend no longer calls them): `/api/workflow/manifest|resume|progress|activity*`,
  `PUT /api/workflow/models`, `/api/prompts/generated*`, `/api/runs*`, `/api/events`, `/api/workflows*`, `/api/harness/*`,
  `/api/specs/*`. `GET /api/workflow/models` now returns only `default`, `default_ref`, `models`, `warnings`.
  `/api/results*` is served by `backend/v5/results.py`. Plan path is fixed per alias (LCA-main → main_plan.md,
  LCA-revise → revise_plan.md). Kept small pieces: `core/agents/{assignment_models (default model only), catalog,
  inspect, errors}`, `core/contracts/session_launch_spec`, `core/runtime/model_profiles`; the workspace lock moved into
  `services/workspace_clean.py` (same `runs/_run/orchestrator.lock` the v5 runner holds). Harness: `prompts/`,
  `permissions/`, `settings.yaml`, `specs/01..04` + `specs/shared`, `workflows/LCA-*.yaml`, `tools/mcp/spec_mcp`,
  `tools/mcp/lca_artifacts`, `tools/host_action`. Scripts: `workflow.py`, `inspect_run.py`, `session_export.py`
  (`npm run inspect|session` removed); `doctor.py` is now a v5 config self-check; `npm start` no longer syncs
  workflow copies. Frontend: `/harness` pages + header button, plan-page "工作流编排"/"预览执行" tabs
  (workflow-board, preview-board, workflow-yaml), `components/runs/*`, `lib/{run-activity,run-status,workflow-manifest}`.
  Kept on purpose: `harness/tools/shared/**` and `control_openlca/workflow_mcp.py` + `mcp.yaml` (proj_init and the
  pi_driver fallback still point at them); pi-runtime TS untouched.
- C8 (done): specs `paragraph`, `summary`, `lca-intake`, `lca-bom` (schema), `lca-mapping` (schema), `lca-report`;
  nodes `write-paragraph`, `summarize`, `lca-intake`, `lca-bom`, `lca-mapping`, `lca-report`; workflows `demo-write`,
  `demo-swapped`, `demo-single`, `full-lca` (4 stages). LCA method rules moved to `harness/rules/lca/` (+ new
  `openlca.md` for the standalone openLCA MCP). openLCA path arguments (`lci_dir` read, `operation_dir` write) are
  checked against the agent's v5 scope inside the MCP (`path_scope.py`, globs passed as `V5_*_GLOBS` env).
  Acceptance tests `t_v5/test_acceptance.py`, `t_v5/test_openlca_path_scope.py`.
  Known gap vs. the old engine: no inventory/mapping/report machine-check profiles yet (schema checks only); the
  report node saves raw calculation output itself (standalone MCP has no render_report_tables / reconcile_import).
- C9 (done): `/runs` = v5 run panel with the agreed testids; `/api/v5/workflows` carries read-only node/agent cards;
  API test `t_v5/test_api.py`. See `docs/refactor/v5/GUI.md`.
- Commit A (rules as YAML): `harness/rules/global/*.yaml` (title, description, enabled, order, applies_to, prompt),
  `harness/rules/lca/*.yaml`, `harness/rules/roles/<role>.yaml` (prompt, access, deliver{submit artifact|verdict, spec,
  max_nudges, max_turns, timeout_min}), `harness/specs/<id>.yaml` (description, schema, checks). `{{var}}` templating
  with values from `config.DEFAULT_VARS` + `project_category`; undefined variable = load error naming file and variable.
  YAML errors report `file:line:col`. `produces[].spec` defaults to the executor role's `deliver.spec`.
  New demo workflow `demo-missing-input` (requires preflight error in the GUI). Workspace clear keeps tracked README.md.
