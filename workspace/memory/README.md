# Workflow Memory

Whole-LCA 运行时在此目录维护固定的运行证据：

- `manifest.json`
- `handoffs/`
- `reviews/`
- `stages/`
- `logs/<run_id>/`：`progress.txt` 与各 turn 排障快照（prompt、argv、stdout、session-ref、rendered）
- 编排检查点 SQLite

除本说明文件外，运行产物不纳入版本控制。`clean_dir` 会清掉本目录（含 logs）；跨次保留请先拷走。
