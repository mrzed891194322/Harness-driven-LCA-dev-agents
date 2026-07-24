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

Windows 用户也可以运行 `src/scripts/_launch_gui.bat`。启动后访问
<http://127.0.0.1:7860>。

## 当前功能边界

项目初始化 Tab 始终位于最左侧并默认打开，“终端显示”Tab 始终位于其后。
参考资料上传、目录清理、RAG 构建、环境检查、openLCA 连接检查和终端日志
控制仍由 GUI 处理。

快捷操作区的“清空文件输入”会同时清除参考资料与参考数据上传组件中的
当前选择，不删除已经同步到 `workspace/` 的文件。

侧栏的“开始LCA工作”始终可用，用于打开“计划制定”Tab。该面板按
`ui/assets/template/plan.md` 动态渲染结构化表单，完全忽略已有的
`workspace/inputs/plan.md`。`<!-- PLAN_TEXTBOX -->` 是唯一输入判定标记，
其后的“用户填写内容区”区块会在原位显示为 Textbox；其他 Markdown 原样分段显示。
左侧目录直接使用 `#`、`##` 两级标题的完整文字。最多 20 个输入区域由固定的
Markdown/Textbox 交替组件池动态更新；无标记的普通 Markdown 作为只读计划显示。
上传 `.md` 只替换当前页面的暂存内容，只有点击“执行LCA计划”时才会保留当前
模板结构、写入字段并原子保存到唯一计划输入 `workspace/inputs/plan.md`。
旧显式 `PLAN_INPUT` 注释不再支持。

面板内执行按钮需要环境、openLCA 两项检查均通过；带输入区域的计划还需任一字段有内容，
无输入标记的 Markdown 计划可直接执行。不可用时
悬停显示“请检查环境连接及填写计划”。执行后 GUI 调用 OpenCode
`whole-lca` 命令，并根据 `workspace/memory/manifest.json` 展示完成或提前
中止结果。完成后，`workspace/outputs/reports/lca_report.md` 直接显示在
“LCA执行结果”Tab；用户可下载报告或按需打开
`workspace/outputs/LCI/human_readable_mapping.md`。LCI 映射不会在页面初次加载时
出现。“修改LCA评估”会重新打开同一计划制定面板。“修改LCI清单”当前仅
作为禁用的功能占位按钮显示。

旧的需求表单、计划输出和计划修改 Tab 不再创建，LCI 制定 Tab 已移除。

## 开发约定

- 外部路径必须通过 `config.py` 配置；Tab 展示用 Markdown 使用项目根目录
  相对路径集中声明，当前脚本路径位于 `src/scripts/`。
- LCA 状态必须读取结构化 manifest；不得仅凭命令退出码或终端文本宣称完成。
- 用户上传文件先写入 `workspace/inputs/references/{file,data}`，初始化时再同步到 RAG 输入目录。
- 修改 GUI 代码后，必须从仓库根目录运行 GUI 测试：

  ```bash
  uv run python -m unittest discover -s src/test -v
  ```

- 提交前同时运行 `git diff --check`。测试不得修改真实 `workspace` 运行产物。
