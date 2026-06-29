# LCA Agent 控制面板 UI 脚本 (src/GUI)

本目录下的 Python 脚本用于构建并运行本 LCA 项目的 Gradio 网页控制台界面。

## 目录结构

- `main.py`：GUI 唯一启动入口，加载环境变量、配置导入路径，并启动 Gradio 服务。
- `ui/`：界面层代码与静态资源。
  - `ui_main.py`：组装 Gradio Blocks 主界面、主题、CSS、按钮事件与任务流。
  - `components/`：可复用界面组件。
    - `terminal_console.py`：构建“终端显示”标签页、终端输出框、状态框和清空按钮。
    - `plan_input.py`：构建“计划输入”标签页，读取计划模板并生成目录导航与输入表单。
    - `left_sidebar.py`：构建左侧“文件交换区”和“快捷操作区”，并返回三个快捷任务按钮。
  - `assets/`：UI 静态资源与模板。
    - `css/style.css`：自定义 Gradio 样式，包括左右主区域整高布局、左侧文件交换区与快捷操作区布局、终端显示区、状态栏、计划输入区、目录导航和按钮布局。
    - `template/plan.md`：LCA 执行计划输入模板，供“计划输入”界面解析与写入。
- `utils/`：底层工具逻辑。
  - `executor.py`：封装 `opencode` 命令执行、流式终端输出、日志清洗和 GUI 快捷任务。
  - `log_exporter.py`：封装 GUI 命令日志导出的路径、目录创建和文件写入逻辑。
  - `plan_loader.py`：解析计划模板、提取/保存用户填写内容，并生成计划目录导航 HTML。
- `log/`：GUI 运行日志目录。
  - `raw_command_output.log`：最近一次命令执行的原始完整日志。

## 依赖说明

本模块使用 `gradio` 作为图形化渲染引擎。运行前需要确保项目环境已同步：

```bash
uv sync
```

## 运行方式

在项目根目录下运行：

```bash
uv run python src/GUI/main.py
```

启动后访问 [http://127.0.0.1:7860](http://127.0.0.1:7860) 查看控制台界面。

## 当前界面功能

- **文件交换区**：左侧使用标签页预留“参考资料”和“参考数据”两个多文件上传视图，当前仅展示 UI，不绑定实际处理逻辑。
- **快捷操作区**：
  - **初始化 RAG 数据库**：执行 `opencode run --command init-rag-database --dangerously-skip-permissions`。
  - **制定 LCA 执行计划**：打开右侧“计划输入”标签页，基于 `ui/assets/template/plan.md` 生成可填写表单。
  - **设计 LCI 数据**：执行 `opencode run --command design-lci --dangerously-skip-permissions`。
- **左侧布局**：文件交换区与快捷操作区共用左侧栏视口可用高度；文件交换区填充剩余空间，快捷操作区保持在底部。
- **右侧布局**：右侧标签页区域作为统一工作区与左侧栏使用同一页面可用高度；每个右侧面板使用 `right-workspace-panel` 填满可用空间，并在面板内部自行分配滚动区和操作区。
- **终端显示**：流式展示命令输出，自动清理 ANSI/OSC 控制序列、回车刷新字符和退格字符。
- **计划输入**：
  - 从模板中的用户填写区生成输入框。
  - 从模板标题生成左侧目录导航。
  - 支持加载已有 `.md` 计划文件并回填输入框。
  - 点击“执行计划”后将结果写入 `input/plan.md`，再执行 `make-plan` 任务。
- **日志导出**：命令原始完整日志写入 `src/GUI/log/raw_command_output.log`。

## 路径约定

- GUI 静态资源统一放在 `src/GUI/ui/assets/` 下。
- CSS 文件放在 `src/GUI/ui/assets/css/` 下。
- 计划模板放在 `src/GUI/ui/assets/template/` 下。
- GUI 产生的日志统一保存到 `src/GUI/log/` 下。

## 维护规范

- **可复用原则**：修改或拓展功能时，应优先复用 `ui/components/` 和 `utils/` 中的既有组件与工具逻辑，避免新建重复的控制台脚本。
- **终端渲染原则**：命令输出优先使用 Gradio 原生文本组件流式展示，避免将 CLI 日志解析成自定义 HTML 后塞入对话组件。
- **模板同步原则**：如果调整 `ui/assets/template/plan.md` 的用户填写区格式，需要同步检查 `utils/plan_loader.py` 的解析、加载和保存逻辑。
- **说明文档更新**：修改或新增 GUI 代码逻辑时，必须同步更新本 `README.md`。
