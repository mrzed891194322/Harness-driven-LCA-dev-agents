# LCA Specification Index

This directory is the source of truth for LCA task specifications, templates, and evaluation criteria.

Agents must use this file as a routing index only. Read the smallest relevant specification entry for the current task, then follow that entry's own disclosure path. Do not load every specification file at once.

`public/` contains only contracts shared by multiple stages. A schema, template, or deterministic validator used by one stage belongs under that numbered stage package. Each numbered package provides a non-normative `schema_mapping.md` maintenance index for its shared and stage-local handshake dependencies.

## Routing

### Plan Guidelines

Use `plan-guidelines/README.md` when the task involves creating or updating an LCA execution plan, todo list, assumptions, data requirements, or project-level workflow.

### LCI Construction

Use `lci-construction/README.md` when the task involves converting an LCA plan into structured Flow, Process, or Product System JSON, validating LCI data, or importing data into openLCA.

### Whole-LCA Workflow Run

When a task starts from an existing execution plan, first read `public/README.md` for the shared runtime and artifact contracts. Then read only the current numbered stage package:

1. `01-plan-quality-gate/README.md`
2. `02-evidence-retrieval/README.md`
3. `03-lci-construction/README.md`
4. `04-lci-quality-evaluation/README.md`
5. `05-openlca-preflight-confirmation/README.md`
6. `06-openlca-import-readback/README.md`
7. `07-lcia-calculation-reporting/README.md`

Do not load all seven stage specifications at startup. Move through them in order and follow each package's own references.

### Revise-LCA Workflow Run

When a task starts from an existing LCA result plus
`workspace/inputs/revise.md`, first read `08-lca-revise-pipeline/README.md`,
then follow `harness/pipelines/LCA-revise.md`. The revision intake is specific
to that package; stages 02–07 continue to use the numbered Whole-LCA packages.
