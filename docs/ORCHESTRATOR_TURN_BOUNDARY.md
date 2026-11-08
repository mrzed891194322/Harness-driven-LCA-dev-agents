# Accepted submit is a host execution boundary

Baseline: `64aecb59cffc1570b5432ad54f835c0b5fd94faa`.
Scope: runtime, submit publication, and driver retry boundary. No workflow/prompt,
role, validation, model parameter, timeout budget, or benchmark changes.

## Contract

- The first validated submit atomically publishes complete JSON without replacement.
  A concurrent later call reports `already_submitted` and cannot replace the winner.
- Workflow sessions execute a model's tool batch sequentially. Tools preceding a
  submit still execute; after the commit no sibling tool starts, including writes.
- The result hook requests SDK abort without awaiting it inside the hook. The
  wrapped `finishTurn` preserves the SDK's persistence/boundary hook, then returns
  `end`; abort alone in SDK 1.3.0 can enter another provider stream with an already
  aborted signal. The outer `session.prompt` is the settlement barrier.
- An accepted reviewer `reject` is a handoff too. A rejected submit (invalid done,
  missing artifact, invalid verdict) creates no commit, so correction is allowed.
- Dispatch ends only the current host segment, not the graph. The driver archives
  the commit and existing graph routing starts the indicated role once. A later
  host segment reuses the conversation but resets the guard.
- Re-entry fences an existing session before modifying context or the commit slot.
  An idle session's commit left by a lost RPC reply is consumed without a new
  prompt. A failed fence or a still-active old segment fails closed rather than
  automatically reusing storage: remote MCP cancellation is not proof that a
  remote operation stopped. Such failures need coordinator review.
- No durable exactly-once claim is made across host/process crashes or independent
  competing workflow runners. The graph has no new durable checkpoint protocol.

Sequential execution changes concurrency for workflow tools, not their permissions.
`max_turns` still counts SDK turn-end events (excluding provider errors); it is not
LangGraph round count. No limit was lowered. `same_tool_limit` remains a separate
fingerprint guard and is not the accepted-submit boundary.

## Offline validation

Use this checkout as cwd; all test workspaces are temporary. Existing dependency
binaries were reused, with a worktree-local ignored node_modules link; no packages
were installed or SDK versions changed.

```
npm run build -w @harness/pi-runtime
node --import tsx --test src/pi-runtime/src/*.test.ts
PYTHONPATH=src python -m pytest src/tests/t_workflow/test_pi_driver.py src/tests/t_workflow/test_session_continuity.py src/tests/t_workflow/test_review_gate.py src/tests/t_workflow/test_settle.py src/tests/t_workflow/test_submit_rights.py src/tests/t_harness/tools/submit -q
npx tsc --noEmit -p src/frontend/web/tsconfig.json
```

Runtime: 50 passing tests, including four real installed AgentSession tests with
an offline scripted stream, real extension hooks and actual tool scheduling.
Python focused suite: 40 passing tests. Includes real submit validation/publication
with 40 racing calls, invalid done correction, reviewer reject, exact graph dispatch
order, lost-reply recovery, failed idle fence and in-flight cancellation refusal.
Existing review gate and permission tests remain passing. Runtime build and web
typecheck pass. No real model/HTTP request is part of these boundary tests.

Final wider workflow + submit suite: 195 passed, 28 failed.
The wider workflow suite is not green on the baseline: 28 failures in acceptance,
API/service, plan/progress, revise and runner tests were individually reproduced by
running the same seven files from a tracked-file export of unmodified 64aecb59 in
/tmp (28 failed, 30 passed). They include fake-workflow recursion-limit failures.
The skill's named t_backend/test_workflow_launch.py and test_workflow_progress.py
are absent in this version; actual workflow tests were run instead.

## Next-stage deployment and rollback (not performed)

1. Record service identity, current 64aecb59 version, protected stopped launchers,
   and confirm no active new task. Preserve original experiment snapshots and
   existing state using the established non-secret backup procedure.
2. Use a separate deployment snapshot of the fix commit. Build its Pi runtime
   (`npm run build -w @harness/pi-runtime`); dist output is ignored, not committed.
   Backend, submit MCP source and Pi runtime must come from this same version.
3. Through the normal project service entry point, replace only the identified
   backend/Pi/web service set. `src/scripts/dev.mjs` expects built Pi output and
   starts backend, Pi, web in order. Check the existing service launch arrangement
   before selecting a checkout. Do not run a broad stop that includes protected
   batch/launcher processes; do not resume or recreate old in-memory runs.
4. Check health and actual runtime version/source path. Create a NEW diagnostic
   snapshot/TAG and run only Spark bom-extract-04 case
   `bom-d210b616-51c0-4aad-8439-c71f6e23112f` if that authorized model is available.
   Availability was not probed in this coding task. Do not fall back to a different
   model or continue the old launcher if unavailable.
5. Observe one accepted dispatch, one handoff, no further provider request in that
   segment, one executor start; then one reviewer start per legitimate dispatch.
   Preserve real checklist/claims, reviewer read-only behavior, reject/rework,
   latest approve-before-done, schema/host checks and strict official scoring.
   A completed label alone is not evidence of correct artifacts.
6. Roll back by stopping only the new service set and selecting the preserved
   64aecb59 deployment snapshot with its matching built runtime. Do not git-reset
   the frozen root or other worktrees. Keep new diagnostic artifacts separate;
   rollback does not authorize restarting any old run or matrix.

No deployment, service restart, model generation, scoring or batch was performed.
The old raw session.jsonl was absent; the existing Cursor result and stop-record
were read as historical evidence, not presented as a newly verified raw trace.
Protected PIDs were not visible in this execution process view, so their current
T/Z state cannot be independently certified here. No signals were sent.
