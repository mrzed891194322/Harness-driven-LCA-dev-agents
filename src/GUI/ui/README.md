# UI 界面与事件绑定层 (`src/GUI/ui`)

本目录包含用户界面组件、样式、静态资源以及核心事件绑定映射。

## 组件布局

所有 UI 控件都已模块化，并在 `components/` 目录中定义，然后统一在 `ui_main.py` 中组装：

- **[ui_main.py](ui_main.py)**：主布局构建器。它定义了页面主题、注入自定义 CSS、实例化 `components/` 中的所有组件，并调用 `events.py` 中的事件绑定器。
- **[components/left_sidebar.py](components/left_sidebar.py)**：
  - **文件上传标签页**：参考资料上传（`ref_materials_file`）与参考数据上传（`ref_data_file`）的交互界面。
  - **任务动作按钮**：触发后台工作流的快捷按钮：
    - `run_btn`：项目初始化 (🚀 项目初始化)
    - `make_plan_btn`：打开/切换计划输入面板 (🧭 制定 LCA 执行计划)
    - `design_lci_btn`：开始设计 LCI 数据 (🧬 设计 LCI 数据)
- **[components/terminal_console.py](components/terminal_console.py)**：
  - `output_console`：展示后台命令标准输出流的主终端文本框。
  - `status`：状态展示框，显示当前执行状态（`Ready`、`Running`、`Stopped`、`Finished`）。
  - `clear_btn`：清空终端日志内容。
  - `stop_btn`：停止当前正在执行的后台任务进程。
- **[components/plan_input.py](components/plan_input.py)**：
  - 根据 plan.md 模板中的可填区块自动生成表单输入框。
  - 自动渲染左侧目录导航栏（TOC）。
  - 包含清空（`clear_fields_btn`）、加载已有计划（`load_plan_btn`）、执行计划（`exec_plan_btn`）以及关闭（`close_btn`）等控制按钮。

---

## 事件与功能调用关系表

所有控件的交互事件统一在 **[events.py](events.py)** 中配置和绑定。以下是界面操作与后端逻辑的路由关系表：

| 触发控件 | Gradio 事件 | 绑定的处理函数 | 调用的后端 API / 动作 |
| :--- | :--- | :--- | :--- |
| **项目初始化按钮** (`run_btn`) | `.click()` | `run_project_init_flow` | `functions.project_init.main.main` |
| **制定计划快捷按钮** (`make_plan_btn`) | `.click()` | *内联 lambda 表达式* | 切换右侧 Tab 面板显示状态 |
| **设计 LCI 快捷按钮** (`design_lci_btn`) | `.click()` | `run_design_lci` | `functions.utils.executor.main.main("design-lci")` |
| **清空日志按钮** (`clear_btn`) | `.click()` | *内联 lambda 表达式* | 重置终端输出为空，状态为 `"Ready"` |
| **停止工作按钮** (`stop_btn`) | `.click()` | `stop_working_task` | `functions.utils.process_manager.trigger_stop()` |
| **加载已有计划文件** (`load_plan_btn`) | `.upload()` | `read_user_plan_values` | `functions.utils.file_loader.main.main("load_values")` |
| **执行计划提交按钮** (`exec_plan_btn`) | `.click()` | `run_exec_plan_flow` | `functions.make_plan.main.main(values)` (内部路由 `functions.utils.file_loader.main.main("save_values")`) |
