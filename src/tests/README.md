# Tests (v5)

Principle: clear everything, keep only what's needed, add slowly. Every test runs in temp dirs; nothing writes to the
real `workspace/` (incl. `workspace/artifacts/plan/`), and live openLCA ports are blocked (`conftest.py`).

- `uv run pytest src/tests` — `t_v5/` (host locks, YAML loading and `{{var}}` rendering, end-of-node decision,
  graph flow, resume, write boundary, demo acceptance) + `t_harness/tools/control_openlca/test_write_guards.py`,
  `test_readonly_scope.py` (openLCA project-category lock).
- `npm run test -w @harness/pi-runtime` — `settle_guard` (nudges, max_rejections, turn/time limits) and `path_guard`
  (write boundary, plan read-only).
- `npm test -w @harness/web` — `/runs` select and model dropdown helpers.

What was deleted and why: `docs/refactor/v5/ISSUES.md` I-15.
