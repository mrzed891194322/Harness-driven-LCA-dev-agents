# 先定位

| 用户在说 | 先看 | 做到什么程度算接上 |
| --- | --- | --- |
| 计划、参考资料、工作流怎么配 | `src/frontend/web/app/plan/page.tsx`，`components/plan/` | 表单和资料写入 `harness/knowledge/plan/main_plan.md` 与 `harness/knowledge/inputs/`；执行时编排器读到的就是这份内容 |
| 点「执行LCA任务」没有开始，或跳转不对 | `components/plan/preview-board.tsx`，`POST /api/workflow/start`，`services/workflow_launch.py` | 按钮保存当前表单，后台启动 `whole-lca` 或 `revise-lca`，浏览器进入 `/runs` |
| 运行详情没有字，或清理阶段一直停在一句提示 | `GET /api/workflow/progress`，`services/workflow_service.py`，`workflow_launch.py` 的 `_consume` | 准备阶段的输出逐段出现；编排器写下 `progress.txt` 后，页面改显示该文件并保持追加 |
| Agent 正文、工具调用没有进终端 | `src/backend/core/agents/progress.py`，`src/backend/pi_client/process.py`，`pi-runtime/src/session_host.ts` | Pi 的 `turn.progress`（以及工具起止）写成 `progress.txt` 里已有的带标签文本，由 `/runs` 解析 |
| 跑完看不到报告，或结果页出现历史运行 | `src/frontend/web/app/results/page.tsx`，`workspace/outputs/`，`workspace/records/` | 结果页只渲染 workspace 里的产物和记录。要展示的 `.local` 内容先复制进 workspace，见 `.cursor/rules/workspace-files.mdc` |
| 模型、密钥、openLCA 不可用 | `/status`，`/api/diagnostics/environment`，设置里的模型档案 | 诊断与「预览执行」使用同一套就绪条件；未就绪时不要启动 |

工作流文件固定为 `src/backend/workflows/LCA-main.yaml`（`whole-lca`）和 `src/backend/workflows/LCA-revise.yaml`（`revise-lca`），见 `services/workflow_cli.py` 的 `WORKFLOW_YAML_BY_TASK`。

要改这些 YAML 的内容时，改读 `.agents/skills/harness-edit/SKILL.md`，不要在 `code-dev` 里直接改装配。
