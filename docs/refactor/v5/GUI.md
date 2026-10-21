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
