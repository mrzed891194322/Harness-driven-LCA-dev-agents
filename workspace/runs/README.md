# workspace/runs

运行期产物根目录（路径中不含 run id；run id 仅在 `.local/runs/<run_id>/`）。

- `_run/`：编排器锁、SQLite、manifest、progress、返工记录（whole-lca 清理时保留 `orchestrator.lock` 与本目录 README）。
- `<stage-id>/<role>-<n>/`：单次尝试（handoff、review、session、raw、checks、sources、import-operations）。
- `<stage-id>/attempts.json`、`accepted.json`：宿主维护的尝试列表与验收快照。

审查通过的 deliverable 复制到 `workspace/artifacts/`。
