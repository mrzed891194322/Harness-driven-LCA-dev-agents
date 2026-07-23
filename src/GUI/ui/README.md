# GUI UI 层

`ui/` 负责组装 Gradio 页面、定义组件和绑定当前仍支持的事件。

## 组件

- `components/left_sidebar.py`：参考资料/数据上传区和快捷操作按钮。
- `components/tab_initial.py`：项目初始化状态检查、清理、RAG 和 openLCA 操作。
- `components/tab_terminal.py`：终端输出、状态、清空和停止任务。
- `components/tab_plan.py`、`components/tab_lci.py`：保留的历史计划/LCI 组件；相关执行按钮当前禁用。

## 事件绑定

- `events/left_sidebar.py`：当前只绑定项目初始化面板入口和关闭动作。
- `events/tab_initial.py`：绑定项目初始化相关功能。
- `events/tab_terminal.py`：绑定日志清空和任务停止。
- `events/tab_lci.py`：只读加载已有 LCI 映射报告，不执行 LCI 制定命令。
- 计划事件模块保留供后续恢复，但不由 `events.bind_ui_events` 注册。

修改 UI 或事件代码后，必须从仓库根目录运行：

```bash
uv run python -m unittest discover -s src/test -v
```
