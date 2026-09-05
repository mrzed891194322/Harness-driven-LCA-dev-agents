# LCA Agent GUI

本目录是项目 Gradio 控制面板的源码目录。GUI 的正确位置是
`src/GUI/`，不要再使用仓库根目录下的 `GUI/` 路径。

## 目录结构

- `main.py`：GUI 启动入口。
- `config.py`：仓库根目录、工作目录和脚本路径的统一配置。
- `ui/`：Gradio 组件、事件绑定和静态资源。
- `functions/`：项目初始化、文件处理、进程管理等后端逻辑。
- `log/`：GUI 运行时日志目录。

## 启动

在仓库根目录运行：

```bash
uv run python src/GUI/main.py
```

启动后访问 <http://127.0.0.1:7860>。关闭终端或按 `Ctrl+C` 结束 GUI。

## 当前功能边界

“终端显示”Tab 始终位于最左侧并作为启动后的默认页。“设置&初始化”与“计划制定”
一样由左侧按钮打开，启动时不显示。页内为左侧配置目录与右侧可滚动详情，
点击目录进入对应配置项：初始化检查、AI Agent 工具、开发者选项。
可选择 AI Agent（codex / claude / opencode / dsh / antigravity）：点 Agent 名称按钮从设置页下方打开配置抽屉，编辑 `.env` 参数后点「保存配置」或「关闭」收起。「测试此配置」会对该页做 live ping，不解锁执行。
「开始初始化检查」会依次对所选 worker 做 live ping（`agent_sdk.check`）并探测 openLCA，两项全部通过后才解锁「执行LCA计划」。
侧栏「用户资料上传」仅暂存于 GUI；点击「执行LCA计划」或「执行改进」时，先 `clean_dir --preset`，再经 `file_sync` 写入 `harness/knowledge/` 与 `workspace/inputs/`。所选 Agent 写入仓库根目录 `.env` 的 `HARNESS_AGENT`。

「开发者选项」中的“查看LCA结果(仅开发过程使用)”会读取已有的
`workspace/outputs/reports/lca_report.md`，打开同名 Tab，并提供报告下载。
报告缺失或不可读时面板会显示原因，不会保留上一次加载的正文。
关闭计划面板会回到“终端显示”。

“计划制定”“LCA评估修改面板(功能开发中)”“LCA评估结果”三个文档型
Tab 共用同一个 Markdown 文档视图：左侧为 Markdown 标题目录，右侧为滚动正文，
每个 Tab 使用独立组件前缀、标题锚点和暂存 State。视图会隐藏可选 YAML
front matter；若文档包含完整的 `PLAN_TEXTBOX` 区域，则在原位置显示 Textbox，
否则仅显示 Markdown。三个 Tab 均预创建 21 个 Markdown 片段和 20 个 Textbox，
因此文件加载后无需动态挂载 Gradio 组件。「工作细节」是独立 JSON 面板，不用该组件池。

侧栏的“开始LCA工作”始终可用，用于打开“计划制定”Tab。该面板按
`ui/assets/template/plan.md` 动态渲染结构化表单，完全忽略已有的
`workspace/inputs/plan.md`。`<!-- PLAN_TEXTBOX -->` 是唯一输入判定标记，
其后的“用户填写内容区”区块会在原位显示为 Textbox；其他 Markdown 原样分段显示。
左侧目录直接使用 `#`、`##` 两级标题的完整文字。最多 20 个输入区域由固定的
Markdown/Textbox 交替组件池动态更新；无标记的普通 Markdown 作为只读计划显示。
上传 `.md` 只替换当前页面的暂存内容。点击「执行LCA计划」时先清理（`knowledge`、
`workspace`、`openLCA`）再同步计划与用户资料，最后启动 agent；同步后才写入
`workspace/inputs/plan.md`。
默认模板不含 YAML front matter；上传计划可省略 front matter，也可携带任意
metadata，GUI 会原样保留而不校验类型或版本。
旧显式 `PLAN_INPUT` 注释不再支持。

面板内执行按钮需要「初始化检查」两项全部通过；带输入区域的计划还需任一字段有内容，
openLCA 检查使用有界请求并在首次失败后重连 3 次，全部失败时保持执行按钮禁用，
无输入标记的 Markdown 计划可直接执行。不可用时
悬停显示“请先完成初始化检查并填写计划”。执行后 GUI 按设置页所选 Agent 启动 Python 主编排（`src/scripts/lca_orchestrator/main.py`），终端只消费编排器 stdout，并根据 `workspace/memory/manifest.json` 展示完成或提前
中止结果。停止时杀掉编排器进程组。完成后，`workspace/outputs/reports/lca_report.md` 直接显示在
“LCA评估结果”Tab；左侧目录可导航报告章节，正文在独立滚动区域内渲染，
用户可下载报告或按需打开「工作细节」，上下渲染
`workspace/outputs/inventory/extracted-bom.json` 与
`process-mapping.json`（Gradio JSON 树）。该 Tab 始终保持挂载，但其导航入口
仅在打开工作细节时显示；底部“关闭面板”只返回 LCA 结果并隐藏导航入口，不再卸载 Tab。
结果文档若包含 `PLAN_TEXTBOX` 也会显示原位输入框，但当前不会把这些
临时输入写回报告文件。
“修改LCA评估”打开独立、常驻挂载的“LCA评估修改面板(功能开发中)”Tab。该面板每次打开都
重新加载 `ui/assets/template/revise.md`，可在内存中暂存最多 20 个
`PLAN_TEXTBOX` 输入区域的 `.md` 改进方案。初始化检查通过、意见非空，
且现有 plan、manifest、LCI 和最终报告齐备时启用“执行改进”；点击后原子保存到
`workspace/inputs/revise.md` 并按所选 Agent 调用 `revise-lca`。成功后结果 Tab
重新加载被覆盖的 `lca_report.md`，失败时读取 revise manifest 展示原因。
“关闭面板”返回 LCA 结果。“修改工作细节”当前仅
作为禁用的功能占位按钮显示。

GUI 使用 `config.py` 中本地优先的学术衬线字体栈显示中英文界面，不依赖在线字体；
代码片段与终端输出继续使用同文件配置的等宽字体栈。

旧的需求表单、计划输出和计划修改 Tab 不再创建，LCI 制定 Tab 已移除。

## 开发约定

- 外部路径必须通过 `config.py` 配置；Tab 展示用 Markdown 使用项目根目录
  相对路径集中声明。
- LCA 状态必须读取结构化 manifest；不得仅凭命令退出码或终端文本宣称完成。
- 用户上传文件在执行前由 `file_sync` 写入 `harness/knowledge/`；不要在上传时直写磁盘。
- 修改 GUI 代码后，必须从仓库根目录运行 `src/test` 回归（GUI 为路径与
  `build_ui()` 冒烟，计划解析与写盘逻辑在同目录其余模块）：

  ```bash
  uv run pytest src/test -v
  ```

- 提交前同时运行 `git diff --check`。测试不得修改真实 `workspace` 运行产物。
