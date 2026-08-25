# LCA Specification Index

This directory is the source of truth for LCA workflow contracts, stage specifications, templates, and deterministic validators.

Agents must use this file as a routing index only. Read the smallest relevant specification entry for the current task, then follow that entry's own disclosure path. Do not load every specification file at once.

`public/` contains only contracts shared by multiple stages. A schema, template, or deterministic validator used by one stage belongs under that numbered stage package. Each numbered package provides a non-normative `schema_mapping.md` maintenance index for stage-local handshake dependencies; shared handoff patterns live in `public/references/handshake-common.md`.

## harness/ four-layer roles

| Directory | Question it answers | Normative for |
| --- | --- | --- |
| `knowledge/` | What user reference files exist? | Uploaded reports and data; not workflow gates |
| `specs/` (this tree) | What must each stage produce and when does it pass or stop? | Whole-LCA / Revise stage order, schemas, handoffs, validators |
| `rules/` | How must agents behave when reading files or calling tools? | Cross-stage discipline (directory bounds, LCA method, openLCA) |
| `tools/` | How are MCP tools implemented? | Signatures, CLI, tests |

Placement rule: stage enter/pass/stop gates belong in `specs/`; reusable agent discipline belongs in `rules/`; implementation detail belongs in `tools/`. Full definitions: `harness/rules/directory-structure/references/harness-structure.md`.

## Routing

### Whole-LCA workflow run

When a task starts from an existing execution plan, first read `public/README.md` for shared runtime and artifact contracts. Then read only the current numbered stage package:

1. `01-plan-quality-gate/README.md`
2. `02-evidence-retrieval/README.md`
3. `03-lci-construction/README.md`
4. `04-lci-quality-evaluation/README.md`
5. `05-openlca-preflight-confirmation/README.md`
6. `06-openlca-import-readback/README.md`
7. `07-lcia-calculation-reporting/README.md`

Orchestration adapters load `harness/workflows/LCA-main.md`. Do not load all seven stage specifications at startup.

### Plan authoring and intake

- Plan template: `src/GUI/ui/assets/template/plan.md`
- Execution-plan quality gate (Whole-LCA stage 01): see stage `01-plan-quality-gate` above

Standalone plan authoring does not use a separate top-level package; follow the template and, when running Whole-LCA, stage 01.

### LCI construction

Use `03-lci-construction/README.md` when converting an approved plan into structured Flow, Process, or Product System JSON, running LCI validation, or preparing data for openLCA preflight.

### Revise-LCA workflow run

When a task starts from an existing LCA result plus `workspace/inputs/revise.md`, first read `08-lca-revise-workflow/README.md`, then follow `harness/workflows/LCA-revise.md`. Revision intake is specific to package 08; stages 02–07 continue to use the numbered Whole-LCA packages.
