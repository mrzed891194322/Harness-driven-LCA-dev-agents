# Workflow Records

Whole-LCA 运行时在此目录维护固定的运行证据：

- `manifest.json`
- `handoffs/`
- `reviews/`
- `evidence/`
- `rework/`
- `import-operations/`
- `logs/<run_id>/`：`progress.txt` 与各 turn 排障快照（prompt、argv、stdout、session-ref、rendered）
- `sessions/`：运行结束时从 `.local/runs/<run_id>/sessions/` 复制的本轮会话快照，另含 `injection-summary.json`。运行过程中的原件仍在 `.local/runs/`
- 编排检查点 SQLite

除本说明文件外，运行产物不纳入版本控制。`whole-lca` 会清掉本目录（含 logs 和 sessions，保留 `orchestrator.lock`）；`revise-lca` 不清 workspace。跨次保留的会话在 `.local/runs/`，不必从这里拷走。结果页只渲染本目录和 `workspace/outputs/`，规则见仓库 `.cursor/rules/workspace-files.mdc`。
