# v5 issues log

Rule: when a problem comes up, pick a fix, keep going, and log it here. Each entry: **what happened**,
**cause**, **fix taken**, **pending Du Yuan** (what still needs a decision or confirmation). Newest at the bottom.

## I-01 pi-runtime socket path too long in worktrees
- What: `npm run dev` from `.local/wt/...` failed to start pi-runtime (Unix socket bind error).
- Cause: Unix socket paths are limited to ~108 bytes; the default `.local/run/pi-runtime.sock` under the nested
  worktree path exceeds it.
- Fix: start worktree services with `PI_RUNTIME_SOCKET` set to a short path (documented in `SERVE_DEV.md`).
- Pending: whether to make a short socket path the default (e.g. under `$XDG_RUNTIME_DIR`) instead of an env var.

## I-02 Dev edits broke live GUI tests
- What: an uncommitted spec move in the worktree made the live services return 400
  `missing harness/specs/paragraph/spec.md` during 模拟操作员's GUI acceptance.
- Cause: services ran from the same worktree that was being edited; they read harness files live.
- Fix: separate read-only serve worktree `.local/wt/serve/202606-harness-agent-LCA` on a detached commit; services run
  only from there; dev work happens in `.local/wt/202606-harness-agent-LCA` (`SERVE_DEV.md`).
- Pending: none (process change). Serve is moved only with `git checkout --detach <hash>` once no run is live.

## I-03 GWP gap vs baseline (deferred)
- What: the full 4-stage v5 run (`44fcfaacf32e4b65a920d8f416e02658`) completed, but GWP differs from the baseline
  (Case1 223.67 / Case2 790.09 / Case3 787.93 / Case3-S 786.58).
- Cause: modelling choices by the agents (extra moulding processes, different transport datasets), not a code bug.
- Fix: none yet; deferred on Du Yuan's instruction to finish the refactor first.
- Pending: decide which choices the specs/rules should pin to match the baseline.

## I-04 Old /api/workflow polling
- What: the old GUI polled `/api/workflow/manifest|progress|activity` and `/api/workflows`; after v5 these returned
  old-engine data or nothing.
- Cause: the old engine's run view; v5 status lives in `/api/v5/status|events`.
- Fix: C7c deleted the old routes and their frontend callers; `/runs` polls only `/api/v5/status` every 2 s.
- Pending: whether to replace polling with SSE later.

## I-05 /runs workflow-select reset after refresh
- What: after a refresh, `workflow-select` went back to `full-lca`; since the table only shows run status when the
  selected workflow matches the run's, it showed 4 pending LCA nodes for a finished demo run.
- Cause: the select was initialised to a constant; nothing synced it with the run.
- Fix: `def5338` — on load the select follows the current/latest run's workflow until the user picks one
  (`lib/initial-workflow.ts`, 4 node:test cases).
- Pending: GUI confirmation by 模拟操作员 on serve.

## I-06 Template variables come from a code table
- What: `{{var}}` in rules/roles/specs is rendered from `DEFAULT_VARS` in `backend/v5/config.py`
  (`language`, `project_category`).
- Cause: Commit A scope ("for now, take variable values from a default table in code").
- Fix: undefined variables are a load error naming file and variable.
- Pending: where variables should come from long-term (plan, settings page, `.env`).

## I-07 deliver defaults need tuning
- What: `max_nudges=2`, `max_turns=80`, `timeout_min=45`, `max_rejections=5` are guesses.
- Cause: no LCA run yet under the new end-of-node decision.
- Fix: defaults in `Deliver`; overridable per role in `rules/roles/<role>.yaml`.
- Pending: tune after the next full LCA run (look at `nudge`, `rejected_retry`, `turn_aborted` events).

## I-08 Backend-disconnect label untested
- What: the GUI's backend-offline / disconnected status label has no test and was not exercised in acceptance.
- Cause: no frontend test setup until now (node:test on `lib/*.test.ts` was added in `def5338`).
- Fix: none yet.
- Pending: whether 模拟操作员 should cover it (stop backend, check the label) or a unit test is enough.

## I-09 revise-lca missing in v5 (resolved, see I-16)
- What: v5 has no revise workflow; `LCA-revise.yaml` was deleted with the old engine. The plan page still has the
  "revise" mode and its `revise_plan.md`.
- Cause: v5 C8 only ported the 4-stage `full-lca`.
- Fix: none yet.
- Pending: Du Yuan's go for revise-lca v5 (next item).

## I-10 Credential copies to clean up
- What: runtime files were copied (not linked) into worktrees: `.env`, `.local/credentials/` (anthropic, deepseek,
  openai, opencode-go, pi-auth, pi-models, pi-agent), `.local/workflow-models.json`, `.local/model_profiles.json` in
  both `.local/wt/202606-harness-agent-LCA` and `.local/wt/serve/202606-harness-agent-LCA`.
- Cause: services must run from the worktrees.
- Fix: none yet (still needed while services run from serve).
- Pending: remove the dev-worktree copies when no longer needed; remove serve copies when the worktree is retired.
  Key rotations in the main repo do not propagate — copy again.

## I-11 /harness browser removed
- What: C7c (`9e6c851`) deleted the `/harness` pages, the header button and `/api/harness/*`.
- Cause: it was built on the old layout (prompts/, permissions/, injection preview).
- Fix: removed.
- Pending: whether a read-only viewer for v5 YAML (rules/roles/specs/workflows) is wanted.

## I-12 Model picker
- What: the plan page's workflow tab, which held the default-model choice, was removed in C7c, leaving no UI to
  choose the model.
- Cause: it was part of the old workflow board.
- Fix: `20f9d30` — `model-select` on `/runs` (uses `/api/workflow/models` + `POST /api/models/selection`), 3 tests.
- Pending: per-node/per-role model choice (old engine had per-assignment overrides) — not ported.

## I-13 Old resume route now 404
- What: `POST /api/workflow/resume` and `/api/runs/{id}/resume-preview` returned 410 after C7b; C7c removed them,
  so they now return 404.
- Cause: no frontend caller left; v5 resume is `POST /api/v5/resume {workflow}`.
- Fix: removed; `test_api.py` expects 404.
- Pending: none unless an external script still calls it.

## I-14 max_rejections
- What: schema/submit rejections were counted as missing submits (spent nudges).
- Fix: `5881ed4` — rejections don't spend nudges; `deliver.max_rejections` (default 5) per node+role (all rounds),
  then abort with `too_many_rejections` (event of the same name).
- Pending: whether the limit should be node-wide across executor and reviewer (now per role file).

## I-15 Test suite pruned to v5 essentials
- What: after C7c the suite still had 429 tests (Python 355 + 13 subtests, pi-runtime 59, scripts 8, web 7), most for
  the old engine/layout or for tool internals, and `conftest.py` wrote minimal plan files into the real
  `harness/knowledge/plan` on every test.
- Cause: tests accumulated with the old engine; C7c only removed those that no longer imported.
- Fix (principle "clear everything, keep only what's needed, add slowly"), now 102 tests:
  - Kept Python (75): all `t_v5/` — host lock 1 plan read-only and lock 2 write boundary (`test_access`,
    `test_acceptance` write-boundary/rerun), lock 3 openLCA category (`test_access::test_openlca_category_lock`,
    `test_category_constant`, `test_openlca_path_scope`, `control_openlca/test_write_guards.py`,
    `test_readonly_scope.py`); YAML loading and variable rendering (`test_rules_yaml`, `test_config`, `test_layout`,
    `test_inject`); end decision (`test_settle`: no_submit, max_turns, timeout, too_many_rejections, submit
    validation); graph flow and resume (`test_runner`, `test_service`, `test_api`, `test_pi_driver`); demo acceptance
    (`test_acceptance`).
  - Kept pi-runtime (20): `settle_guard.test.ts`, `path_guard.test.ts`. Kept web (7): `/runs` select and model
    dropdown helpers (asked for explicitly).
  - Deleted Python: `contracts/`, `t_backend/` (credentials, plan form, tutorial, workflow models, openLCA db,
    knowledge preserved), `t_core/` (runtime protocol), `t_harness/` control_openlca tool internals (v2, workflow_mcp,
    readonly_mcp, cleanup*, ipc_timeout, import_identity, transport_units, get_not_found, preflight, health),
    `t_harness/lca_artifacts/*`, `t_repo/*`, `t_scripts/*` (workspace_clean, proj_init, entrypoint smoke) and
    `support/` — old layout, or not one of the v5 essentials.
  - Deleted pi-runtime: activity, auth_materialize, endpoint, injection, lifecycle, live_models, protocol, server,
    session_release, turn_outcome. Deleted scripts: `platform.test.mjs`, `status.test.mjs`.
  - `conftest.py` no longer writes to `harness/knowledge/plan`; it only sets a temp workspace and blocks live openLCA
    ports. Verified: plan file hashes unchanged after a full run.
- Pending: which deleted areas to bring back first (likely candidates: credentials service, openLCA cleanup/import
  tool internals, pi-runtime session lifecycle/release), one at a time.

## I-16 revise-lca v5 design decisions
- What: v5 needed the old LCA-revise (清单修订 → 映射修订 → 报告修订, driven by `revise_plan.md`) reading the
  previous full-lca artifacts as `requires`.
- Cause/constraint: a fresh v5 run wiped all of `workspace/artifacts`, and a node clears its own produce dir before it
  starts, so a revise node could not read and rewrite the same `bom/`, `mapping/`, `report/` paths.
- Fix taken:
  - Workflow fields `revise_of` and `plan_file`. A fresh `revise-lca` run moves the earlier artifacts to
    `artifacts/previous/` (event `previous_snapshot`), keeps `artifacts/plan/` (original `main_plan.md`) and writes
    `revise_plan.md`. Revise nodes produce the normal paths with the unchanged `lca-bom`/`lca-mapping`/`lca-report`
    specs and require `previous/<dir>`; `previous/` is read-only (only `requires` grants read).
  - Base rule: the base is replaced only after a completed run (full-lca or revise-lca). After a failed/stopped
    revise, the existing `previous/` stays the base and the half-revised artifacts are discarded.
  - No 01 intake gate (old revise had a reviewer-only gate); `lca-bom-revise` requires `plan/main_plan.md`,
    `plan/revise_plan.md` and `previous/bom`, so a missing earlier run or empty revise plan fails before any agent turn.
  - Rules: `rules/lca/revise.yaml` (shared: intent first, full not diff, keep unaffected rows/UUIDs, reviewer judges
    intent before method) + `revise-bom|mapping|report.yaml` condensed from the old `stages/*.revise|reviser.md`.
    No new roles or specs.
  - `lca-report` spec: `operation_dir` now says "this node's runs dir" so `lca-report-revise` stays inside its own
    write boundary.
  - GUI start: `POST /api/workflow/start {workflow: revise-lca}` ignores the main-plan form fields the /runs panel
    sends and uses the saved revise plan (plan page "修订" mode, `LCA-revise` alias); empty → 400 with a clear message.
    Aliases `revise-lca` / `LCA-revise` accepted. Fixed: the start route loaded the workflow from the real repo
    instead of the service root.
- Pending Du Yuan:
  - Whether to bring back the intake gate for revise (validate `revise_plan.md` is actionable before 清单修订).
  - openLCA: the revise report re-imports into the project category; unchanged foreground UUIDs overwrite the
    previous import (same category). No cleanup of entities the revision removed — confirm acceptable.
  - Whether `revise_of` should check the base run's workflow (now any completed run is a valid base).
  - Not yet run against real openLCA/model.

## I-17 Stop during the last turn was swallowed
- What: on serve 759a658, run 3e32e874: run-stop clicked during the summarize review turn; the run still ended
  `completed` and no stop event was logged.
- Cause: the runner only checked `stop_requested()` between turns; `V5Service.stop()` only set a flag (no event, no
  abort of the turn in progress); nothing checked after the final turn.
- Fix: `stop()` logs `stop_requested` at once and calls `driver.cancel()` (PiDriver → `session.cancel` → pi
  `session.abort`, the same path as a turn abort). The runner checks stop after every turn and after every node
  (including the last); a stop ends the run `stopped` (`run_end status=stopped`), never `completed`. A turn that
  still returned an accepted submit/verdict is honoured (node stays `passed`); an aborted turn marks the node
  `stopped` (resumable). Stops between turns now also end `stopped` instead of `failed`.
- Pending: confirm on serve with a real model that `session.cancel` interrupts a long tool call promptly.

## I-18 Model preflight failure invisible in the node table
- What: runs c43d8cb7, ef4e3b0d: preflight failed, every node row stayed pending, `node-error` empty; the message
  appeared only in run-reason.
- Cause: the runner returned before any node status was written.
- Fix: the first node to run gets status `failed`, reason `model_preflight`, the message in its error
  (`node-error`), and a `node_end` event. 429 / rate-limit and 503 / overloaded errors are prefixed with a clear
  Chinese explanation (`explain_model_error`).
- Pending: whether to retry the preflight automatically on 429/503 before failing.

## I-19 Frontend page inventory at 802866a (static; fix list, nothing fixed yet)

Method: listed every `app/**/page.tsx` and shared header component, every `/api/...` call in `app/`, `components/`,
`lib/`, compared with the `@app.*` routes in `src/backend/api/app.py` at 802866a, and probed the GET shapes read-only
on the serve backend. **Every path the frontend calls still exists** and the probed shapes (`/api/diagnostics/environment`,
`/api/results`, `/api/plan`, `/api/references`, `/api/tutorial/catalog`, `/api/credentials/status`,
`/api/models/providers`, `/api/v5/*`) keep the keys the pages read. So the breakage is not 404s but v5 semantics,
removed panels and stale content. Not checked: actual rendering in a browser (needs 模拟操作员/screenshots); there may
be visual breakage this static pass cannot see.

| Page | State |
|---|---|
| `/` , `/settings` | OK (redirect to `/status`) |
| `/status` | OK statically |
| `/plan` | Degraded: two tabs gone, revise mode locked |
| `/runs` | Works, minimal: unstyled, no live activity view |
| `/results` | Degraded: old run model (stages/handoffs) |
| `/tutorial`, `/tutorial/[...slug]` | Works; content stale (describes removed panels) |
| `/harness/**` | Removed (404); still referenced by docs |
| Header: model settings dialog, backend status, tutorial/language buttons | OK statically |

### I-19a `/status` (项目状态)
- Originally: environment checks (Node/pi runtime, Python, openLCA IPC + database, LCA tools), provider list with
  per-provider model lists, openLCA port edit.
- Calls: `GET /api/diagnostics/environment`, `GET|PUT /api/lca/openlca`, `GET /api/models/providers`,
  `GET /api/models/providers/{p}/models` — all present; `node`, `pi_agents`, `python_agent`, `openlca`, `lca_tools`,
  `available_providers` still returned. C7c dropped `harness_specs` and `local_workflows`, which the page does not read.
- Broken: nothing found statically.
- Fix: none; confirm visually.

### I-19b `/plan` (LCA 计划)
- Originally: four tabs — 用户填写 (study form, template download, plan import), 参考资料 (uploads + notes),
  工作流编排 (old stage graph + per-assignment models: `/api/workflows`, `/api/workflow/models` PUT,
  `/api/harness/document`), 预览执行 (old preview + start: `/api/workflow/start` with stage manifest); new/revise mode.
- Now: C7c removed the last two tabs (their APIs are gone); fields + references work (`/api/plan`, `/api/plan/template`,
  `/api/plan/import`, `/api/references*`, `/api/diagnostics/environment` for the openLCA badge — all present).
- Broken: (1) no way to start a run or see the workflow from this page — start moved to `/runs`, but the page has no
  link/hint; (2) the 修订 mode button is disabled by `lib/revise-lock.ts` (`reviseWorkLocked = true`), so
  `revise_plan.md` cannot be written from the GUI although `revise-lca` (c836ce8) now needs it — starting revise from
  `/runs` returns the 400 "修订计划为空" unless the file was written by hand; (3) the tab bar's prev/next buttons and
  layout were designed for 4 tabs.
- v5 endpoints: `GET/PUT /api/plan?workflow=LCA-revise` (exists), `GET /api/v5/workflows` (for a read-only workflow
  summary).
- Fix: set `reviseWorkLocked = false`; add a "去运行" link to `/runs?workflow=full-lca|revise-lca` after the fields;
  optionally a read-only 工作流 tab rendering `/api/v5/workflows` node cards (title, requires, produces, agents);
  re-check tab layout with 2 tabs.

### I-19c `/runs` (运行详情)
- Originally: run manifest by stage, live activity feed and agent stream (`/api/workflow/progress`,
  `/api/workflow/activity`, `/api/workflow/activity/stream` SSE, `/api/runs/*` sessions/injection), resume from stage.
- Now: `V5RunPanel` — `/api/v5/workflows|status|resume|nodes/{n}/feedback/{r}`, `/api/workflow/start|stop`,
  `/api/workflow/models`, `/api/models/selection`, `/api/plan`; all present.
- Broken/missing: (1) uses inline styles, not the app's panel classes, so it looks out of place next to other pages;
  (2) no event/activity view — `GET /api/v5/events?offset=` exists but nothing shows it (nudges, rejections,
  tool activity, stop_requested); (3) no per-node detail (agent cards from `/api/v5/workflows.details` are fetched
  but only partly shown); (4) `/runs?workflow=` deep link not supported.
- Fix: restyle with existing classes; add an events panel polling `/api/v5/events` (offset-based); show the node
  card (requires/produces/agents) on row click; read `?workflow=` as the initial select (after the run-follow rule).

### I-19d `/results` (结果浏览)
- Originally: current run summary (stage, reason), handoff list per stage/attempt (`runs/**/handoff*.json`),
  deliverables under `artifacts/`, attempt artifacts with grouped `raw/` files, run-level records, zip download.
- Now: `GET /api/results`, `/api/results/file`, `/api/results/archive` served by `backend/v5/results.py` with the old
  shape; `manifest` is the v5 manifest (`current_node`, `nodes`, `workflow`) and `handoffs` is always `[]`.
- Broken: (1) `manifest.current_stage` no longer exists → the current-step line is empty (v5 field
  `current_node`); (2) 工作记录 list shows only `runs/_run` files — no per-node verdicts, since v5 has no handoff files;
  (3) v5 per-node files (`runs/<node>/status.json`, `<role>/submit_round_N.json`, `feedback/round_N.md`,
  `submit_rejections.jsonl`) appear as a flat artifact list; the old `raw/` grouping keys on attempt dirs that v5 does
  not have; (4) `artifacts/previous/` (revise base) is mixed into deliverables.
- v5 endpoints: `/api/v5/status` (nodes, rounds, errors), `/api/v5/nodes/{n}/feedback/{r}`.
- Fix: in `v5/results.py` return `handoffs` built from v5 node status + `submit_round_*.json` (node, role, round,
  verdict/status, summary) and add `current_node`; frontend reads `current_node` (fallback `current_stage`); list
  `artifacts/previous/` as its own group; keep zip as is (decide whether `previous/` goes in the zip).

### I-19e `/tutorial`, `/tutorial/[...slug]` (教程)
- Calls: `/api/tutorial/catalog|document|asset` — present, unchanged.
- Broken: content. `docs/tutorial/README.md` walks through 「工作流编排」/「预览执行」 with screenshots
  (`page-2-3.png`, `page-2-4.png`) that no longer exist in the GUI; `docs/tutorial/panel/run-lca.md` describes
  "初始化检查 → whole-lca 或 revise-lca" (old intake gate and task names).
- Fix: rewrite the plan and run sections for v5 (plan page fields/references → `/runs` workflow + model select →
  start/stop/resume → results), replace the two screenshots, mention revise via the 修订 plan + `revise-lca`.

### I-19f `/harness/**` (removed)
- Originally: harness document browser + injection preview (`/api/harness/catalog|document|injection|components`).
- Now: pages and routes deleted in C7c (I-11); a bookmark or a doc link gives Next's 404.
- Fix: decide with Du Yuan (I-11): either a read-only v5 viewer (rules/roles/specs/workflows YAML via a new
  `GET /api/v5/harness?path=`), or drop and remove remaining doc references.

### I-19g Shared header components
- `model-settings-dialog`: `/api/credentials*`, `/api/models/custom-endpoint(s)` — present, unchanged. OK.
- `backend-status` / `lib/api.ts`: `/api/health` — OK (disconnect label still untested, I-08).
- Fix: none.

### I-19h Found by 模拟操作员 (screenshots `.local/ui-op/v5/pages/`)
1. `/status` hardcoded Pi SDK `1.1.0` (`app/status/page.tsx:280`) → fixed in I-23.
2. `/results` 最终交付 listed `artifacts/plan/main_plan.md` → fixed in I-22.
3. `/results` 修改计划 always disabled → fixed by I-20 (unlock).
4. `/runs` model dropdown always shows the "ollama unreachable" warning as an error → fixed in I-23.
5. Tutorial `basics/openlca` and `panel/overview` stale → fixed in I-23.
- Model-preflight failure in the GUI (I-18): verified by test only (`test_model_preflight_failure_marks_first_node`);
  no fake endpoint or setting was added to trigger it from the GUI.

## I-20 /plan fixes from I-19b (done)
- Fix: `reviseWorkLocked = false` (also enables 修改计划 on `/results`), so the 修改工作 mode writes
  `revise_plan.md` via `PUT /api/plan?workflow=LCA-revise`. New "去运行" link (`data-testid="plan-go-run"`, existing
  `status-start` style) under the plan panels → `/runs?workflow=full-lca` (new) or `/runs?workflow=revise-lca` (revise).
  `/runs` now honours a valid `?workflow=` over the latest-run default (`initialWorkflow(..., requested)`).
- Test: `lib/run-link.test.ts` (link target, unlock, `?workflow=` precedence).
- Pending: the read-only 工作流 tab (I-19b optional) not done; 2-tab layout to be checked visually.

## I-21 /harness rebuild plan (built in I-26; editing still pending Du Yuan)
- Decision proposed: rebuild `/harness` as a read-only v5 YAML viewer with four sections — global rules, roles,
  specs, workflows — queued after the /plan, /results and /runs fixes. It is meant to become the base for GUI editing
  later. No code yet. Pending Du Yuan's confirmation (supersedes the open choice in I-11/I-19f).

## I-22 /results fixes from I-19d (done)
- `v5/results.py` now fills `handoffs` with per-node verdict rows built from `runs/<node>/status.json` and
  `runs/<node>/<role>/submit_round_N.json` (node in manifest order, then round, executor before reviewer;
  `status` = executor status or reviewer verdict, `status_reason` = summary/feedback (200 chars), `node_status`).
  The 工作记录 tab shows them as 节点结论 (labels: 通过/退回/完成/失败; reviewer verdicts are `pass`/`fail`, found in the serve smoke).
- `artifacts/previous/**` gets `category: "previous"` and its own 上一版 tab, shown only when present.
- `artifacts/plan/**` (main_plan.md, revise_plan.md) is excluded from 最终交付 (I-19 item 2 from 模拟操作员); the zip
  download still includes all of `artifacts/`.
- The page header shows `状态 · 当前节点 <current_node>` (fallback `current_stage`), `data-testid="results-run-line"`.
- 修改计划 button: enabled by I-20 (`reviseWorkLocked = false`), links to `/plan?mode=revise` (I-19 item 3).
- Tests: `src/tests/t_v5/test_results.py`, `lib/result-kind.test.ts`.

## I-23 Status version, model note, tutorials (done)
- `/status`: Pi SDK version comes from `diagnostics/environment.pi_agents.version`, read from the installed
  `src/pi-runtime/node_modules/@earendil-works/pi-coding-agent/package.json`, else the pin in `src/pi-runtime/package.json`
  (`pi_sdk_version`, test `test_pi_version.py`). The other toolchain versions on that card are still hardcoded (pending:
  read them too, or drop them).
- `/runs`: model warnings (e.g. ollama unreachable) render as a muted `settings-help` hint prefixed 提示：.
- Tutorials rewritten for v5: `basics/openlca.md` (project category, background data read-only), `panel/overview.md`
  (current pages, no /harness, node/round model), and `panel/run-lca.md` (full-lca / revise-lca via /runs).
  Pending: `docs/tutorial/README.md` still shows the removed 工作流编排/预览执行 screenshots (needs new screenshots).

## I-24 /runs restyle, events panel, node detail (done; I-19c)
- Restyled with the app classes; status badges per run/node; same core testids.
- Events panel from `/api/v5/events` (offset polling, last 500 kept, reset on a new run): nudges, rejected_retry,
  submit_rejected, too_many_rejections, no_submit, turn_aborted, stop_requested, stop_cancel_failed,
  requires_failed, model_preflight, review verdicts, node/run start/end; 显示全部 shows every kind.
- Node detail on clicking a node name: produces/requires/max rounds, agent table (model, tools, rules, read/write),
  node error, that node's events.
- Testid change for 模拟操作员: `node-card-<id>` removed (cards now only in the detail); new `node-open-<id>`,
  `node-detail-<id>`, `node-events-<id>`, `events-panel`, `event-row[data-kind]`. See GUI.md.
- Test: `lib/run-events.test.ts`. Pending: no visual check yet (after the serve switch).

## I-25 /status toolchain versions from the environment (done)
- `diagnostics/environment.toolchain` = {typescript, next (web `node_modules`, then the hoisted root `node_modules`), npm, uv (`--version`,
  cached per process), pi_sdk (I-23), python (`sys.version`)}. The page shows only versions that could be read;
  nothing is hardcoded anymore. Test: `test_pi_version.py::test_toolchain_reads_packages_and_blanks_missing`.
- Note: npm/uv are looked up on the backend's PATH; if the service PATH lacks them they are dropped from the card.

## I-26 /harness read-only v5 YAML viewer (done; I-21, I-19f)
- Backend `GET /api/v5/harness` (`backend/v5/harness_view.py`): four sections — 全局规则 (`rules/global` plus
  node-level rule folders such as `rules/lca`, grouped by folder), 角色 (`rules/roles`), 规格 (`specs`), 工作流
  (`workflows/*.yaml` plus `workflows/nodes/*.yaml`). Per file: parsed `fields`, `raw` text, and `error`
  {message, line} from the real loaders (`load_rule`, `load_role_def`, `load_spec`, `load_workflow`, `load_node`),
  so YAML syntax errors, schema errors and undefined `{{var}}` show exactly as a run would fail. Read-only; paths are
  fixed under `harness/`.
- Page `/harness` (app styles: results columns, kind tabs, `agent-table`, `results-source`): field table + numbered
  raw YAML with the error line highlighted; error banner `file:line — message`; error count badge in the header.
  Header link `data-testid="header-harness"`. Testids: `harness-viewer`, `harness-tab-<section>`,
  `harness-file-<path>`, `harness-fields`, `harness-raw`, `harness-file-error`, `harness-error-count`.
- Tests: `test_harness_view.py` (real harness loads clean; YAML and template errors carry file and line),
  `lib/harness-view.test.ts`.
- Pending Du Yuan: GUI editing on top of this viewer; whether `rules/lca` belongs under 全局规则 or its own section.
- Note: `ruff check src/backend/api/app.py` reports 3 pre-existing B008 (FastAPI `File`/`Form` defaults), not new.

## I-27 Chinese state labels in events; tutorial for v5 (done)
- One shared label map `lib/labels.ts` (run/node states + verdicts: 通过/退回/完成/失败/已停止/…) used by the /runs
  table and badges, the events panel (`describeEvent`: review verdict 通过/退回, node/run end states) and /results
  (`VERDICT_LABEL` re-exports it). `tsconfig.json` gets `allowImportingTsExtensions` (noEmit) so lib files can import
  each other with `.ts` for the node test runner. Test: `run-events.test.ts`.
- `docs/tutorial/README.md` rewritten for v5: plan → 去运行 → /runs (workflow, model, start/stop/续跑, events, node
  detail) → results → revise (available). Removed the 工作流编排/预览执行 sections and deleted `page-2-3.png`,
  `page-2-4.png` (no matching shot; the retaken `page-3.png` is the /runs screenshot). `openlca-ipc.png` kept.
- Copied 模拟操作员's 5 retaken shots (`page-1`, `page-2-1`, `page-2-2`, `page-3`, `page-4`) over the old images.
- `panel/overview.md`, `panel/run-lca.md`: 继续 → 续跑, 模型设置 → 设置 (match the UI).

## I-28 Provider "Connection error." burned all nudges in 48 s (fixed)
- What happened: full-lca run 4825c79d on serve 741325c (16:13 UTC+8). Preflight ok, then the lca-intake executor's
  turns ended with `stopReason: "error"` / "Connection error." three times in a row (16:13:25–16:14:13). The settle
  guard treated each errored turn as "no submit": nudge 1, nudge 2, then `no_submit` → node failed, run failed.
  The network to opencode.ai was flaky at the time (1 of 3 curl probes timed out; `/api/models/test` ok right after).
- Cause: SettleGuard only knew "submitted or not"; a provider error looked like an agent that forgot to submit, and
  nudges fire immediately with no wait.
- Fix: `turn_end` passes the assistant message to the guard. If the last turn ended with `stopReason: "error"`,
  `beforeSettle` waits (`model_retry_delays_s`, default 10/30/60 s), then continues with a "上一次模型请求失败…继续"
  message — no nudge spent; logged as `model_retry`. After the delays are used up the turn ends with
  `abort_reason: "model_error"` (node reason `model_error`, not `no_submit`). `beforeSettle` is now async (pi awaits
  boundary handlers). Events panel label 模型请求失败，重试. Tests: two new cases in `settle_guard.test.ts`.
- Pending Du Yuan: retry count and waits (code default, not yet a deliver field); errored turns still count toward
  `max_turns`.

## I-29 Model preflight fails on a single network blip (fixed, not yet exercised live)
- What happened: rerun c17274f2 on serve e4817b8 (16:18:55 UTC+8) failed at preflight in 34 s with
  "Connection error." Probes from the lab PC to `opencode.ai/zen/go/v1/models` at the time: about 1 in 6 requests
  failed to connect (5 s), the rest 200 in ~1.1 s; baidu.com always 200. So the upstream/route is flaky, not the key.
- Cause: preflight made exactly one request; any blip failed the whole run.
- Fix: `PiDriver.preflight` retries transient errors (connection/timeout/ECONN*/fetch failed/502/503/504) after
  10 s and 30 s; auth errors and others fail at once. Each attempt logs `model_preflight` with `attempt`.
  Test: `test_preflight_retries_transient_errors_only`.
- Pending: serve not switched to this commit and no third run started (the one allowed rerun was used by c17274f2);
  waiting for the go-ahead. Network flakiness to opencode.ai should be checked by Du Yuan.

## I-30 submit MCP intermittently not ready → node failed as no_submit (fixed)
- What happened: full-lca run 85e9e615 on serve ce1c217 (16:24:25 UTC+8). Preflight hit a 503 on attempt 1 and passed
  on attempt 2 (I-29 worked). lca-intake passed in round 1 (executor 2:41, reviewer 0:41, 0 nudges). Creating the
  lca-bom executor session then waited the full 90 s (16:28:22 → 16:29:53) for the `submit` MCP server to register
  tools, failed, and the node was reported as `no_submit`. The error pointed to a `*.mcp.log` that pi-mcp never
  writes. Started by hand with the same mcp.json, the submit server answers initialize in 0.4 s, so the server is
  fine; the hang is on the pi-mcp connect side and did not repeat for intake. Root cause not found.
- Fix: pi-runtime retries session creation once when an MCP server is not ready (`withMcpRetry`, logged to the
  pi-runtime stderr as `mcp_retry`); the message no longer points to the non-existent log; Python maps it to node
  reason `mcp_not_ready` instead of `no_submit`. Tests: `mcp_retry.test.ts`, `test_mcp_not_ready_is_its_own_reason`.
- Pending: root cause in pi-mcp (connect race?) — keep an eye on `mcp_retry` lines in the serve log.
- Update (rerun fac7df55 on serve 59a95e3, 16:33:10–16:40:11 UTC+8): **not intermittent**. Preflight blip again
  (attempt 1 "Connection error.", attempt 2 ok), lca-intake passed round 1 (executor 2:17, reviewer 0:57, 0 nudges),
  then the lca-bom executor's `submit` MCP again never registered: attempt 1 timed out after 90 s (`mcp_retry 1/1`
  in `.local/logs/pi-runtime.log`), attempt 2 ran past the Python 180 s `session.create` timeout, so the node again
  ended as `no_submit` ("pi-runtime 请求超时: session.create"), not `mcp_not_ready`.
- Ruled out: the server itself (same mcp.json by hand: initialize and tools/list answer in <0.5 s for both intake
  and bom), env size (bom 1.2 KB vs intake 0.2 KB). pi-mcp writes nothing to the configured log, so no client-side
  trace. Pattern: the first node's sessions (executor + reviewer, both with a `submit` server) work; the next
  node's first session in the same pi-runtime process cannot connect its `submit` server. demo-write (2 nodes)
  passed at 16:07 on 741325c, so it may depend on timing/what the previous sessions left behind.
- Next steps (not done, rerun budget used): enable pi-mcp debug output or wrap the server command with a stderr
  tee to see whether pi spawns it at all; check whether shutting down the previous node's sessions closes a shared
  MCP manager; raise the Python `session.create` timeout above 2×90 s so `mcp_not_ready` is reported correctly.
- **Root cause found (16:5x UTC+8):** pi 1.3.0's MCP extension resolves every MCP `env` value as a config value
  (`pi-coding-agent/dist/extensions/mcp/runtime.js` → `resolveConfigValueOrThrow`): `$NAME`/`${NAME}` are env
  references and a leading `!` runs a shell command. Commit 9aaf493 (B, after 6cc34b4) started passing the executor's
  produces list inline as `V5_PRODUCES`, including the spec's JSON schema. The lca-bom schema has `"$schema"` and
  `"$id"`, so pi looked for env vars `schema`/`id`, failed to resolve them, and never started the submit server,
  silently: no tools ever registered, hence the 90 s wait. lca-intake's spec has no schema and the demo specs have
  no `$`, so they worked; that is why it looked like "the second node". The serve path length played no part:
  pi-mcp uses stdio, not per-session sockets (checked), and bom's paths are shorter than intake's.
- Cheap repro without a model or openLCA: `.local/tmp/repro_mcp.py <root> <sessions>` (private pi-runtime, temp
  workspace, `session.create` only). Before: `lca-bom.executor` alone fails after 90 s. After: all 8 full-lca
  sessions create in < 1 s each.
- Fix: the produces list goes to `workspace/tmp/pi-v5/<session>/produces.json`, passed as `V5_PRODUCES_FILE`;
  `check_mcp_env` (Python) refuses any MCP env value containing `$` or starting with `!`, and pi-runtime does the same
  in `session.create` (`mcpEnvProblems`) so a bad value fails at once with the server/key named instead of after
  90 s. Logging: pi-runtime logs `<session> create: mcp=<servers>` and `mcp_retry` to `.local/logs/pi-runtime.log`.
  Python `session.create`/`resume` timeout raised 180 → 240 s (`CREATE_TIMEOUT_S`, above 2 × 90 s), so a real
  not-ready case reports `mcp_not_ready`. `PI_MCP_CREATE_ATTEMPTS` (default 2) controls the create retry.
- Regression tests: `test_settle.py::test_mcp_env_has_no_pi_template_syntax` (a spec with `$schema`/`$id` → no `$`
  in any MCP env; produces file keeps the schema), `mcp_retry.test.ts` (`mcpEnvProblems`).
