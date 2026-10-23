# v5 workspace artifacts and revise-lca revisions (I-45)

## Layout
- `workspace/artifacts/plan/` — plan files (`main_plan.md`, `revise_plan.md`); always read-only for agents. The /plan form saves here too (I-47); full-lca start clears `revise_plan.md`.
- `workspace/artifacts/<dir>/` — node deliverables (`bom/`, `mapping/`, `report/`); a node may write only the
  dirs of its `produces`.
- `workspace/runs/<node>/` — per-node status, submits, feedback, reviewer notes; `runs/_run/` — manifest,
  `events.jsonl`, `orchestrator.lock`, `revisions.json` (revise runs).
- `workspace/tmp/` — scratch (pi sessions under `tmp/pi-workflow/`).

A fresh full-lca clears `artifacts/` (except `README.md`), `runs/` (keeps the lock) and `tmp/`.

## revise-lca: rev files next to the originals
- No `artifacts/previous/`. A fresh revise keeps every artifact untouched (it clears only `runs/` and `tmp/`).
- Unit of revision = one entry directly inside a produce dir: a file (`bom/bom.json`, `bom/bom.md`,
  `report/results.json`) or a dir (`mapping/LCI/`, `report/raw/`). The original is rev 0.
- Revision N is written next to the original with `.rev<N>` before the extension:
  `bom.rev1.json`, `bom.rev1.md`, `LCI.rev1/`, `lca_report.rev2.md`, `raw.rev2/`. Paths inside the files use the
  rev'd names (e.g. `results.rev1.json` → `raw.rev1/...`).
- N allocation: at the start of a fresh revise run, per produce entry, N = 1 + the highest existing rev of that
  entry (`backend/v5/revisions.py: allocate`). Companions in the same dir use the same N. Saved in
  `runs/_run/revisions.json` and the manifest `revisions` field (event `revisions_allocated`).
- Resume (`/api/workflow/resume`, 重跑本轮) reloads `revisions.json` and reuses the same N; the interrupted node's rev-N
  entries are cleared and rewritten, originals and other revs stay.
- Before a fresh revise, rev-N entries of nodes that did not pass in the last revise run are deleted
  (event `revision_dropped`), so "latest" never points at a half-written revision. Passed revisions stay.
- Inputs: each `requires` path resolves at node start to the latest version (highest rev, else original). Inside
  the node's own produce dir it resolves to the latest *below* its N (bom-revise rev 2 reads `bom.rev1.json`;
  mapping-revise reads this run's `bom.rev2.json`). Event `node_paths` records the resolved requires/produces.
- produces/checks/specs: the node's `produces` paths are rewritten to rev N, so host checks, JSON-schema checks,
  the submit tool's produces file and `<deliverable_*>` all use the rev'd path. `<deliverable_*>` adds the
  renaming rule for companion files.
- Write guard: rev N entries are writable; every existing original / other rev in the produce dirs is in
  `denied_write_globs` (beats write globs in pi PathGuard).
- `revision` is host-set on the node copy; a node YAML with `revision:` is a config error.
- /results lists rev files with the originals under 最终交付 (old 599ed0a style, no 上一版 tab).
