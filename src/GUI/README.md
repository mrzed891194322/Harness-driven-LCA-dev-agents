# LCA Agent 控制面板 UI 脚本 (src/GUI)

本目录下的 Python 脚本用于构建并运行本 LCA 项目的 Gradio 网页控制台界面。

## 目录结构
- `main.py`：启动入口脚本，仅包含唯一的 `main()` 函数启动 Gradio 服务器。
- `utils/`：存放具体的界面逻辑与底层流式命令执行器。
  - `__init__.py`：将 utils 声明为 Python 子包。
  - `executor.py`：包含使用 `subprocess` 在项目根目录下异步执行 `opencode` 命令并实时输出终端日志的生成器，同时清理 ANSI/OSC 控制序列与回车刷新字符；目前封装了 `init-rag-database`、`make-plan` 和 `design-lci` 三个 GUI 快捷任务。
  - `log_exporter.py`：封装 GUI 命令日志导出的路径、目录创建和文件写入逻辑。
  - `ui.py`：定义 Gradio Blocks 界面布局、色彩主题及原生文本控制台组件。

## 依赖说明
本模块使用了 `gradio` 作为图形化渲染引擎。需要确保环境已完成同步：
```bash
uv sync
```

## 运行方式
在项目根目录下，使用虚拟环境运行以下命令：
```bash
uv run python src/GUI/main.py
```
启动后，固定使用 [http://127.0.0.1:7860](http://127.0.0.1:7860) 查看控制台界面。

## 当前界面功能
- **文件交换区**：左上角使用标签页预留了文件上传与下载视图，当前仅展示 UI，不绑定实际处理逻辑。
- **初始化 RAG 数据库**：执行 `opencode run --command init-rag-database --dangerously-skip-permissions`。
- **制定 LCA 执行计划**：执行 `opencode run --command make-plan --dangerously-skip-permissions`，默认 `$USER_REQUIREMENTS` 为空。
- **设计 LCI 数据**：执行 `opencode run --command design-lci --dangerously-skip-permissions`，默认 `$USER_REQUIREMENTS` 为空。
- **控制台日志**：所有任务共用右侧终端输出框，并将原始日志写入 `src/GUI/log/raw_command_output.log`。

## 维护规范
- **可复用原则**：修改或拓展功能时，应优先在此 GUI 架构中增加对应组件和事件绑定，避免在其他目录新建重复的控制台脚本。
- **日志目录原则**：GUI 产生的日志统一保存到 `src/GUI/log/` 子目录下。
- **终端渲染原则**：命令输出优先使用 Gradio 原生文本组件流式展示，避免将 CLI 日志解析成自定义 HTML 后塞入对话组件。原始完整日志会保存到 `src/GUI/log/raw_command_output.log`。
- **说明文档更新**：在修改或新增代码逻辑时，必须阅读并同步更新本 `README.md`。
