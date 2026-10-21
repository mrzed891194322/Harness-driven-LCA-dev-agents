# v5 GUI (minimal, C9)

`/runs` is now the v5 run panel (`src/frontend/web/components/v5/run-panel.tsx`). The old runs page and its
activity stream are gone from the route (still in git history).

## Selectors (stable, for 模拟操作员)

| testid | element | notes |
| --- | --- | --- |
| `workflow-select` | `<select>` | options = `GET /api/v5/workflows`; default `full-lca` |
| `run-start` | button | reads the saved plan form (`GET /api/plan`) and posts `/api/workflow/start {workflow, ...fields}` |
| `run-status` | `<strong>` | text = Chinese label; attribute `data-status` = idle/running/completed/failed |
| `node-table` | `<table>` | |
| `node-row-<id>` | `<tr>` | `data-status` = pending/running/passed/failed/error/stopped |
| `node-error-<id>` | `<td>` | always rendered; empty when no error |
| extra: `run-stop`, `run-resume`, `run-reason`, `run-error`, `node-feedback-<id>-<round>`, `feedback-view`, `node-open-<id>` (row button, toggles the detail), `node-detail-<id>`, `node-events-<id>`, `agent-card-<id>-<executor|reviewer>` (inside the detail only), `events-panel`, `event-row` (`data-kind`). **Removed:** `node-card-<id>` (the always-visible card list; open the row instead) | | |

## Plan entry (unchanged)

The plan page (`/plan`) form, plan import and reference upload are unchanged (same UI, same endpoints `/api/plan`,
`/api/plan/import`, `/api/references`). Its start button still posts `/api/workflow/start` with `task: whole-lca`,
which v5 maps to `full-lca`. At run start the form content is rendered into `workspace/artifacts/plan/main_plan.md`
(read-only for agents). `revise-lca` has no v5 workflow yet (start returns 400).

## Node cards

Each node shows its deliverables (spec → artifacts path), requires and max rounds; each agent shows model + thinking,
role, tools, rules, and read/write scopes (read-only).

## Model dropdown (/runs)

- `model-select`: lists `GET /api/workflow/models` (`models`, current `default_ref`); changing it calls
  `POST /api/models/selection {profile_id}` and applies to the next run (the v5 service reads the saved default at
  start). Disabled while a run is live. `model-note` shows "已保存" or the error; on error the old value is restored.
- `workflow-select` follows the current/latest run's workflow after a page refresh until the user picks another.
- Frontend unit tests: `npm test -w @harness/web` (node:test on `lib/*.test.ts`).

## /runs layout (I-24)
App styles (`plan-board`, `settings-card`, `section-head`, `run-meta`, `agent-table`, `badge-*`, `status-banner`).
Header: status badge (`run-status`, `data-status` unchanged), run id, current node; start/stop/resume on the right.
Below the node table: feedback view, node detail (click a node name), events panel polling `/api/v5/events?offset=`
every 2 s; it shows control events (nudges, rejections, stops, aborts, preflight, verdicts, node/run start/end) by
default, all events with 显示全部. The event list resets when the log shrinks (a new run).

## /harness (I-26)
Read-only viewer of `harness/` YAML from `GET /api/v5/harness`. Header link `header-harness`. Tabs
`harness-tab-rules|roles|specs|workflows`, file buttons `harness-file-<path>`, `harness-fields`, `harness-raw`,
`harness-file-error` (shows `file:line — message`), `harness-error-count`.

## testid mapping after the 599ed0a 1:1 restore (2026-10-21, I-44)
Rule (Du Yuan): pages look like master `599ed0a`; testids are only attributes on the old elements (no visual change).

| testid | Now on | Notes |
|---|---|---|
| `run-status` (+`data-status`) | /runs 当前阶段 badge | old status values: idle/running/completed/failed/interrupted (v5 `stopped` → `interrupted`) |
| `run-stop` | /runs 中止工作 button (only while running) | |
| `run-side` | /runs 当前阶段 side panel | |
| `run-stage-text` | /runs 当前阶段 text | |
| `run-show-reason` / `run-reason-panel` | /runs 显示原因 button / 失败原因 popup | |
| `run-restart` | /runs 从头重跑 (only when interrupted) | starts the main workflow from the saved plan |
| `run-error` | /runs error banner | |
| `agent-stream` | /runs 实时终端 | fed by `/api/workflow/progress` |
| `activity-summary` | /runs 活动概览 chips | fed by `/api/workflow/activity` |
| `preview-start` | /plan 预览执行 → 执行LCA任务 | the start button now lives here (old location) |
| `workflow-board`, `flow-node-<id>`, `flow-agent-<node>-<role>`, `flow-inspector`, `agent-model-select` | /plan 工作流编排 | per-agent model = old per-assignment model |
| `harness-viewer`, `harness-tab-<section>`, `harness-file-<path>`, `harness-fields`, `harness-raw`, `harness-file-error` | /harness | |
| **removed** `run-start` | → `preview-start` on /plan | |
| **removed** `run-resume` | none (old page had no resume; checkpoint resume awaits Du Yuan) | |
| **removed** `workflow-select` | workflow follows /plan mode (新工作 = full-lca, 修改工作 = revise-lca) | |
| **removed** `model-select`, `model-note` | /plan 工作流编排 默认模型 (`.flow-model`) | |
| **removed** `node-table`, `node-row-*`, `node-open-*`, `node-detail-*`, `node-error-*`, `node-feedback-*`, `feedback-view`, `agent-card-*` | stages show in 实时终端 / 活动概览; feedback in /results 工作记录 | |
| **removed** `events-panel`, `event-row`, `node-events-*` | orchestrator lines in 实时终端 | |
| **removed** `plan-go-run` | none (Du Yuan: removed) | |
| **removed** `results-run-line` | none (not in 599ed0a) | |
| **removed** `harness-error-count` | per-file `harness-file-error` + ⚠ in nav | |
| **removed** `agent-thinking-select` | none (not in 599ed0a; needs approval) | |
| **removed** `preview-injection`, `preview-agent-*` | none (not in 599ed0a; `/api/v5/preview` kept, UI hidden) | |
