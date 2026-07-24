# GUI UI 层

`ui/` 负责组装 Gradio 页面、定义组件和绑定当前仍支持的事件。

## 组件

- `components/left_sidebar.py`：参考资料/数据上传区和快捷操作按钮。
- `components/tab_initial.py`：项目初始化状态检查、清理、RAG 和 openLCA 操作。
- `components/tab_terminal.py`：终端输出、状态、清空和停止任务。
- `components/tab_result.py`：whole-lca 完成/提前中止结果和内嵌的 LCA 报告。
- `components/tab_plan.py`：从 `plan.md` 默认模板生成 `#`/`##` 两级目录，
  并预创建 21 个 Markdown 片段和 20 个 Textbox 组成的原位交替组件池。
- `components/tab_lci.py`：按需显示的只读 LCI 清单及暂未启用的修改按钮；
  不再包含 LCI 制定 Tab。

## 事件绑定

- `events/left_sidebar.py`：保留隐藏的项目初始化入口兼容绑定。
- `events/tab_initial.py`：绑定项目初始化相关功能。
- `events/tab_terminal.py`：绑定日志清空和任务停止。
- `events/tab_plan.py`：每次打开时重载默认模板，上传成功后只替换暂存文档及当前
  Markdown 片段/目录/字段状态，上传失败不改变页面，并维护执行门禁。
- `events/tab_lci.py`：只读加载已有 `human_readable_mapping.md`，不执行 LCI 制定命令。
- `events/tab_result.py`：将结构化字段写回标记模板并保存已校验计划、运行 `whole-lca`、解析 manifest、
  在结果 Tab 展示 LCA 报告并提供下载。

修改 UI 或事件代码后，必须从仓库根目录运行：

```bash
uv run python -m unittest discover -s src/test -v
```
