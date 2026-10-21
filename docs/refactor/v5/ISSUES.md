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
