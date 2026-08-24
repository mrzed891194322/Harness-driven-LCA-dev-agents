# GUI UI 层

`ui/` 负责组装 Gradio 页面、定义组件和绑定当前仍支持的事件。

## 组件

- `components/left_sidebar.py`：参考资料/数据上传区和快捷操作按钮。
- `components/tab_initial.py`：项目初始化状态检查、清理、RAG 和 openLCA 操作。
- `components/tab_terminal.py`：终端输出、状态、清空和停止任务。
- `components/render_mdfile.py`：所有文档型 Tab 共用的
  `MarkdownDocumentView`，统一构建左侧目录、右侧滚动正文、21/20 交替组件池、
  独立锚点与 State，并根据 `PLAN_TEXTBOX` 自动显示输入区。
- `components/tab_result.py`：whole-lca 完成/提前中止结果及使用共享视图的 LCA 报告。
- `components/tab_plan.py`：从 `plan.md` 默认模板初始化共享视图并配置两级目录。
- `components/tab_revise.py`：常驻挂载的“LCA评估修改面板(功能开发中)”表单和 revise-lca 执行按钮。
- `components/tab_lci.py`：常驻挂载、按需加载到共享视图的 LCI 清单及暂未启用的修改按钮。

## 事件绑定

- `events/left_sidebar.py`：绑定侧栏“打开初始化面板”并切换到项目初始化 Tab。
- `events/tab_initial.py`：绑定项目初始化相关功能。
- `events/tab_terminal.py`：绑定日志清空和任务停止。
- `events/tab_plan.py`：每次打开时重载默认模板，上传成功后只替换暂存文档及当前
  Markdown 片段/目录/字段状态，上传失败不改变页面，并维护执行门禁。
- `events/tab_improvement.py`：“修改LCA评估”打开独立改进面板，每次重载默认模板；
  上传只更新该面板内存状态，执行时保存 `workspace/inputs/revise.md`、运行
  `revise-lca` 并把结构化结果交给结果 Tab；关闭返回结果 Tab。
- `events/tab_lci.py`：以单次无队列事件加载并打开已有 `human_readable_mapping.md`，
  通过共享更新函数渲染目录、正文及可选输入区；底部关闭按钮只返回结果 Tab。
- `events/tab_result.py`：绑定侧栏“查看LCA结果(仅开发过程使用)”，通过共享更新函数读取报告；
  同时将计划结构化字段写回标记模板并保存
  已校验计划、运行 `whole-lca`，并统一解析 whole-lca/revise-lca manifest，
  在结果 Tab 展示报告并提供下载。

修改 UI 或事件代码后，必须从仓库根目录运行 `src/test` 回归（GUI 为构建冒烟）：

```bash
uv run python -m unittest discover -s src/test -v
```
