# 尚未接通

用户让「走通」时，先补下面还断着的一跳。接上之后，`/runs` 的解析格式不用改。

1. **准备阶段的输出被吃掉。** `workflow_launch._consume` 只取清理和编排生成器的最终状态，清理脚本的逐行输出不会进入 `/runs`。用户会长时间只看到「正在保存当前计划，并清理上一次运行…」。要把生成器里的新文本写进 launch 缓冲，让 `progress` 能追加。
2. **Pi 的流式事件没有写成进度日志。** `session_host.ts` 会 `emitEvent("turn.progress")`，`process.py` 能挂 `add_event_handler`，但正式 `run_turn` 没有把文本和工具调用交给 `progress.print_session`。`print_session`、`format_tool_start`、`format_assistant` 目前没有调用方。
3. **`services/file_sync.py` 的 `sync_files` 是空操作。** 不要依赖 `executor_console.run_pre_workflow_console` 里的 sync 把 GUI 上传写回磁盘。现在能保住资料，是因为 launch 自己做了快照和恢复。若改清理顺序，必须继续保证 `inputs/` 和计划文件在编排器启动前还在。
4. **编排画布只读。** `workflow-board.tsx` 只 `GET /api/harness/document`。画布上的修改不会写回 `src/backend/workflows/LCA-*.yaml`，执行仍用磁盘上的原文件。用户要求「按 GUI 里的工作流跑」时，要先定义保存位置，再让 `--workflow` 指向那份文件。在那之前，改装配走 `.agents/skills/harness-edit/SKILL.md`，直接改磁盘上的 YAML。
5. **计划表单没有逐字自动保存。** 只有点击执行时，启动流程才把表单写入 `main_plan.md`。执行前进程若中断，磁盘上的计划可能仍是旧的。
