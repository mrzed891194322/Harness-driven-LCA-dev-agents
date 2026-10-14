# 约束与验证

## 约束

- 清理预设 `whole-lca` 会清 knowledge 暂存、`workspace` 生成物和 openLCA。改启动流程时先复制用户资料再清理，失败也要写回。没有用户明确要求时，不要替用户点「执行LCA任务」。
- 界面文案用中文。运行详情保持与计划页相同的整页卡片（`status-fit`、`plan-board`、`settings-card`），终端按阶段、工具行和正文渲染，不要退回整段 JSON。
- 进度文本继续用 `progress.py` 的标签格式。改解析或渲染时，用现有 `progress.txt` 对照。
- 密钥只在设置流里写入 `.local/credentials/`。不要把密钥抄进进度日志、handoff 或提交。
- 结果页只渲染 `workspace/outputs/` 和 `workspace/records/`。运行中必须写在 `.local/runs/` 的内容，在运行结束时复制一份到 workspace。不要让结果页直接读 `.local`，也不要列出历史运行。目录和要改的文件见 `.cursor/rules/workspace-files.mdc`。

## 验证

- Python：`uv run pytest src/tests/t_backend/test_workflow_launch.py src/tests/t_backend/test_workflow_progress.py`
- 前端类型：`npx tsc --noEmit -p src/frontend/web/tsconfig.json`
- 改了页面或启动按钮时，在已运行的控制面板里走一遍：计划预览 → 执行（仅当用户要求真的开跑）→ 运行详情能看到新增文本。只改渲染时，用已有 `progress.txt` 即可，不必再开一轮会清工作区的运行。

改了 harness 的规则绑定后，另跑 `uv run pytest src/tests/t_core -q`。
